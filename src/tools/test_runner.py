"""Test Runner Tool.

Executes pytest against generated code and test suites for the multi-agent workflow.
Provides structured results including pass/fail status, error details, and coverage.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────

DEFAULT_PYTEST_TIMEOUT = 300  # seconds
DEFAULT_PYTEST_MARKERS: list[str] = []
PYTEST_ADDOPTS_ENV = "PYTEST_ADDOPTS"


def run_pytest(
    test_paths: list[str | Path],
    code_dirs: Optional[list[str | Path]] = None,
    working_dir: Optional[str | Path] = None,
    markers: Optional[list[str]] = None,
    timeout: int = DEFAULT_PYTEST_TIMEOUT,
    verbose: bool = False,
    addopts: Optional[list[str]] = None,
) -> tuple[dict[str, Any], bool]:
    """Run pytest against the given test paths and return structured results.

    Args:
        test_paths: List of test file or directory paths to run.
        code_dirs: Directories to add to PYTHONPATH for imports.
        working_dir: Working directory for pytest execution.
        markers: Pytest marker expressions (e.g., ["slow", "not slow"]).
        timeout: Maximum seconds to wait for pytest to complete.
        verbose: Enable verbose output (-v).
        addopts: Additional pytest command-line options.

    Returns:
        Tuple of (results_dict, tests_passed_bool).
        results_dict contains: passed, failed, errors, skipped, duration,
        summary, and raw_output.
    """
    test_paths = [str(p) for p in test_paths]
    code_dirs = [str(d) for d in (code_dirs or [])]
    working_dir = str(working_dir) if working_dir else None

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Verbose mode
    if verbose:
        cmd.append("-v")

    # Markers
    if markers:
        for marker in markers:
            cmd.extend(["-m", marker])

    # Addopts
    if addopts:
        cmd.extend(addopts)

    # Test paths
    cmd.extend(test_paths)

    logger.info("Running pytest: %s", " ".join(cmd))
    logger.debug("Working directory: %s", working_dir or os.getcwd())

    # Set up environment
    env = os.environ.copy()

    # Add code directories to PYTHONPATH
    if code_dirs:
        existing_pythonpath = env.get("PYTHONPATH", "")
        new_paths = ":".join(str(d) for d in code_dirs)
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{existing_pythonpath}:{new_paths}"
        else:
            env["PYTHONPATH"] = new_paths
        logger.debug("Added PYTHONPATH: %s", env["PYTHONPATH"])

    # Run pytest
    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error("Pytest timed out after %d seconds", timeout)
        return _build_timeout_result(timeout), False
    except FileNotFoundError:
        logger.error("pytest module not found — is pytest installed?")
        return _build_error_result("pytest module not found"), False
    except Exception as exc:
        logger.exception("Pytest execution failed: %s", exc)
        return _build_error_result(str(exc)), False

    # Parse results
    output = result.stdout or ""
    errors_output = result.stderr or ""
    combined_output = f"{output}\n{errors_output}" if errors_output else output

    # Extract pytest summary using regex-like parsing
    results = _parse_pytest_output(combined_output, result.returncode)

    tests_passed = result.returncode == 0

    logger.info(
        "Pytest complete: %d passed, %d failed, %d errors, exit_code=%d",
        results["passed"],
        results["failed"],
        results["errors"],
        result.returncode,
    )

    # Store raw output for debugging
    results["raw_output"] = combined_output[:10000]  # Limit to 10KB

    return results, tests_passed


def _parse_pytest_output(output: str, return_code: int) -> dict[str, Any]:
    """Parse pytest output to extract structured results.

    Args:
        output: Combined stdout/stderr from pytest.
        return_code: Pytest exit code (0=pass, 1=fail, 2=error).

    Returns:
        Dict with passed, failed, errors, skipped counts and summary.
    """
    results = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "duration": 0.0,
        "summary": "",
        "return_code": return_code,
    }

    # Parse summary line: "X passed, Y failed, Z errors in Ws"
    import re

    # Look for the final summary line
    summary_match = re.search(
        r"(\d+) passed, (\d+) failed, (\d+) error(s)?, (\d+) skipped",
        output,
    )
    if summary_match:
        results["passed"] = int(summary_match.group(1))
        results["failed"] = int(summary_match.group(2))
        results["errors"] = int(summary_match.group(3))
        results["skipped"] = int(summary_match.group(4))
    else:
        # Try simpler patterns
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        error_match = re.search(r"(\d+) error(s?)", output)
        skipped_match = re.search(r"(\d+) skipped", output)

        if passed_match:
            results["passed"] = int(passed_match.group(1))
        if failed_match:
            results["failed"] = int(failed_match.group(1))
        if error_match:
            results["errors"] = int(error_match.group(1))
        if skipped_match:
            results["skipped"] = int(skipped_match.group(1))

    # Parse duration
    duration_match = re.search(r"in ([\d.]+)(s|ms)", output)
    if duration_match:
        value = float(duration_match.group(1))
        unit = duration_match.group(2)
        results["duration"] = value if unit == "s" else value / 1000.0

    # Extract summary text (last non-empty line before final summary)
    lines = output.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith("=====") and "passed" not in line.lower():
            results["summary"] = line
            break

    # If no summary found, use the return code as indicator
    if not results["summary"]:
        if return_code == 0:
            results["summary"] = "All tests passed"
        elif return_code == 1:
            results["summary"] = "Some tests failed"
        else:
            results["summary"] = f"Pytest exited with code {return_code}"

    return results


def _build_timeout_result(timeout: int) -> dict[str, Any]:
    """Build result dict for a timeout scenario."""
    return {
        "passed": 0,
        "failed": 0,
        "errors": 1,
        "skipped": 0,
        "duration": float(timeout),
        "summary": f"Pytest timed out after {timeout} seconds",
        "return_code": -1,
    }


def _build_error_result(error_msg: str) -> dict[str, Any]:
    """Build result dict for an execution error."""
    return {
        "passed": 0,
        "failed": 0,
        "errors": 1,
        "skipped": 0,
        "duration": 0.0,
        "summary": f"Pytest execution error: {error_msg}",
        "return_code": -2,
    }


def discover_tests(
    directory: str | Path,
    pattern: str = "test_*.py",
) -> list[Path]:
    """Discover test files in a directory.

    Args:
        directory: Directory to search for tests.
        pattern: Glob pattern for test files.

    Returns:
        List of discovered test file paths.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        logger.warning("Test directory does not exist: %s", dir_path)
        return []

    tests = list(dir_path.rglob(pattern))
    # Filter out __pycache__ and hidden directories
    tests = [
        t for t in tests
        if "__pycache__" not in str(t) and not t.name.startswith(".")
    ]
    logger.info("Discovered %d test files in %s", len(tests), dir_path)
    return tests


def run_pytest_json(
    test_paths: list[str | Path],
    code_dirs: Optional[list[str | Path]] = None,
    working_dir: Optional[str | Path] = None,
    timeout: int = DEFAULT_PYTEST_TIMEOUT,
) -> dict[str, Any]:
    """Run pytest with JSON report output for structured results.

    Uses pytest's built-in JSON reporter (pytest-json or --json flag).

    Args:
        test_paths: Test file/directory paths.
        code_dirs: Directories to add to PYTHONPATH.
        working_dir: Working directory.
        timeout: Timeout in seconds.

    Returns:
        Dict with structured pytest results, or error dict on failure.
    """
    import tempfile

    test_paths = [str(p) for p in test_paths]
    code_dirs = [str(d) for d in (code_dirs or [])]
    working_dir = str(working_dir) if working_dir else None

    # Create temporary JSON report file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        report_path = f.name

    cmd = [
        sys.executable, "-m", "pytest",
        "--json-report",
        "--json-report-file", report_path,
        "--json-report-omit", "collectors,start,end",  # Reduce noise
    ] + test_paths

    env = os.environ.copy()
    if code_dirs:
        existing = env.get("PYTHONPATH", "")
        new_paths = ":".join(code_dirs)
        env["PYTHONPATH"] = f"{existing}:{new_paths}" if existing else new_paths

    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Read JSON report
        results = {"raw_return_code": result.returncode}
        if Path(report_path).exists():
            try:
                with open(report_path, "r") as f:
                    json_report = json.load(f)
                results.update(_extract_json_report(json_report))
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to parse JSON report: %s", exc)

        return results

    except subprocess.TimeoutExpired:
        return _build_timeout_result(timeout)
    except Exception as exc:
        return _build_error_result(str(exc))
    finally:
        # Clean up temp file
        try:
            Path(report_path).unlink(missing_ok=True)
        except OSError:
            pass


def _extract_json_report(json_report: dict[str, Any]) -> dict[str, Any]:
    """Extract key metrics from pytest JSON report.

    Args:
        json_report: Parsed pytest JSON report dict.

    Returns:
        Dict with passed, failed, errors, skipped counts and summary.
    """
    results = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "duration": 0.0,
        "summary": "",
    }

    # Count test outcomes from nodes
    for node in json_report.get("nodes", []):
        outcome = node.get("outcome", "")
        if outcome == "passed":
            results["passed"] += 1
        elif outcome == "failed":
            results["failed"] += 1
        elif outcome == "error":
            results["errors"] += 1
        elif outcome == "skipped":
            results["skipped"] += 1

    # Get total duration
    results["duration"] = json_report.get("duration", 0.0)

    # Build summary
    parts = []
    if results["passed"]:
        parts.append(f"{results['passed']} passed")
    if results["failed"]:
        parts.append(f"{results['failed']} failed")
    if results["errors"]:
        parts.append(f"{results['errors']} errors")
    if results["skipped"]:
        parts.append(f"{results['skipped']} skipped")

    results["summary"] = ", ".join(parts) if parts else "No tests collected"
    results["return_code"] = json_report.get("exitcode", -1)

    return results


def get_pytest_version() -> Optional[str]:
    """Get the installed pytest version.

    Returns:
        Version string (e.g., "7.4.0") or None if pytest is not installed.
    """
    try:
        import pytest
        return pytest.__version__
    except ImportError:
        logger.warning("pytest is not installed")
        return None
