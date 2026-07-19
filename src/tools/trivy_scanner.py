"""Trivy Scanner Tool.

Provides Trivy container and filesystem vulnerability scanning for the
multi-agent workflow. Supports both Docker image scanning and direct
filesystem scanning as fallback.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────

DEFAULT_IMAGE_NAME = "app-image:latest"
DEFAULT_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM"]
TRIVY_SKIP_DB_UPDATE = os.getenv("TRIVY_SKIP_DB_UPDATE", "false").lower() == "true"
TRIVY_SKIP_JAVA_DB = os.getenv("TRIVY_SKIP_JAVA_DB_UPDATE", "false").lower() == "true"


def run_trivy_scan(
    image_name: Optional[str] = None,
    target_path: Optional[str | Path] = None,
    severities: Optional[list[str]] = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run Trivy vulnerability scan on a Docker image or filesystem.

    Args:
        image_name: Docker image name to scan (e.g., "app-image:latest").
        target_path: Filesystem path to scan (used if image_name is None).
        severities: Severity levels to report (default: CRITICAL, HIGH, MEDIUM).
        timeout: Maximum seconds for the scan.

    Returns:
        Dict with vulnerabilities, severity_counts, and scan metadata.

    Raises:
        FileNotFoundError: If trivy CLI is not found.
        subprocess.TimeoutExpired: If scan exceeds timeout.
    """
    severities = severities or DEFAULT_SEVERITIES
    image_name = image_name or DEFAULT_IMAGE_NAME

    # Determine scan mode
    if target_path:
        return _scan_filesystem(str(target_path), severities, timeout)
    else:
        return _scan_image(image_name, severities, timeout)


def _scan_image(
    image_name: str,
    severities: list[str],
    timeout: int = 600,
) -> dict[str, Any]:
    """Run Trivy container image scan.

    Args:
        image_name: Docker image to scan.
        severities: Severity levels to include.
        timeout: Timeout in seconds.

    Returns:
        Structured scan results dict.
    """
    if not _is_trivy_available():
        logger.error("Trivy CLI not found — cannot scan Docker image")
        return _build_error_result("Trivy CLI not installed")

    cmd = [
        "trivy", "image",
        "--format", "json",
        "--severity", ",".join(severities),
        "--exit-code", "0",  # Always exit 0 to capture all results
    ]

    if TRIVY_SKIP_DB_UPDATE:
        cmd.append("--skip-db-update")
    if TRIVY_SKIP_JAVA_DB:
        cmd.append("--skip-java-db-update")

    cmd.append(image_name)

    logger.info("Running Trivy image scan: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error("Trivy scan timed out after %d seconds", timeout)
        return _build_timeout_result(timeout)
    except FileNotFoundError:
        logger.error("trivy command not found")
        return _build_error_result("Trivy CLI not installed")

    # Parse JSON output
    if result.stdout.strip():
        try:
            report = json.loads(result.stdout)
            return _parse_trivy_report(report, scan_type="image", image_name=image_name)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Trivy JSON output: %s", exc)
            return _build_error_result(f"Invalid JSON from Trivy: {exc}")

    return _build_empty_result(scan_type="image", image_name=image_name)


def _scan_filesystem(
    target_path: str,
    severities: list[str],
    timeout: int = 600,
) -> dict[str, Any]:
    """Run Trivy filesystem scan.

    Used as fallback when Docker is unavailable or for scanning source code.

    Args:
        target_path: Directory or file path to scan.
        severities: Severity levels to include.
        timeout: Timeout in seconds.

    Returns:
        Structured scan results dict.
    """
    if not _is_trivy_available():
        logger.error("Trivy CLI not found — cannot scan filesystem")
        return _build_error_result("Trivy CLI not installed")

    target = Path(target_path)
    if not target.exists():
        logger.error("Scan target does not exist: %s", target)
        return _build_error_result(f"Target path does not exist: {target}")

    cmd = [
        "trivy", "fs",
        "--format", "json",
        "--severity", ",".join(severities),
        "--exit-code", "0",
    ]

    if TRIVY_SKIP_DB_UPDATE:
        cmd.append("--skip-db-update")
    if TRIVY_SKIP_JAVA_DB:
        cmd.append("--skip-java-db-update")

    cmd.append(str(target))

    logger.info("Running Trivy filesystem scan: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error("Trivy filesystem scan timed out after %d seconds", timeout)
        return _build_timeout_result(timeout)

    # Parse JSON output
    if result.stdout.strip():
        try:
            report = json.loads(result.stdout)
            return _parse_trivy_report(report, scan_type="filesystem", target=target_path)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Trivy JSON output: %s", exc)
            return _build_error_result(f"Invalid JSON from Trivy: {exc}")

    return _build_empty_result(scan_type="filesystem", target=target_path)


def _parse_trivy_report(report: dict[str, Any], scan_type: str, **kwargs) -> dict[str, Any]:
    """Parse a Trivy JSON report into structured results.

    Args:
        report: Raw Trivy JSON report.
        scan_type: Either "image" or "filesystem".
        **kwargs: Additional metadata to include in results.

    Returns:
        Dict with vulnerabilities, severity_counts, and metadata.
    """
    vulnerabilities = extract_vulnerabilities(report)
    severity_counts = count_by_severity(vulnerabilities)

    # Determine if there are critical/high vulnerabilities
    has_critical_high = any(
        v.get("severity") in ("CRITICAL", "HIGH") for v in vulnerabilities
    )

    return {
        "scan_type": scan_type,
        "vulnerabilities": vulnerabilities,
        "severity_counts": severity_counts,
        "total_vulnerabilities": len(vulnerabilities),
        "has_critical_high": has_critical_high,
        "security_passed": not has_critical_high,
        **kwargs,
    }


def extract_vulnerabilities(report: dict[str, Any]) -> list[dict[str, str]]:
    """Extract vulnerability details from a Trivy report.

    Handles both image scan (Results per layer) and filesystem scan formats.

    Args:
        report: Raw Trivy JSON report.

    Returns:
        List of vulnerability dicts with id, severity, package, etc.
    """
    vulns: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    # Handle image scan format (Results array with layers)
    for result in report.get("Results", []):
        for v in result.get("Vulnerabilities", []):
            vuln_id = v.get("VulnerabilityID", "")
            if vuln_id and vuln_id not in seen_ids:
                seen_ids.add(vuln_id)
                vulns.append({
                    "id": vuln_id,
                    "severity": v.get("Severity", "UNKNOWN"),
                    "package": v.get("PkgName", ""),
                    "installed_version": v.get("InstalledVersion", ""),
                    "fixed_version": v.get("FixedVersion", ""),
                    "title": v.get("Title", ""),
                    "description": v.get("Description", ""),
                    "links": v.get("Links", []),
                })

    # Handle filesystem scan format (direct Vulnerabilities array)
    if not vulns:
        for v in report.get("Vulnerabilities", []):
            vuln_id = v.get("VulnerabilityID", "")
            if vuln_id and vuln_id not in seen_ids:
                seen_ids.add(vuln_id)
                vulns.append({
                    "id": vuln_id,
                    "severity": v.get("Severity", "UNKNOWN"),
                    "package": v.get("PkgName", ""),
                    "installed_version": v.get("InstalledVersion", ""),
                    "fixed_version": v.get("FixedVersion", ""),
                    "title": v.get("Title", ""),
                })

    return vulns


def count_by_severity(vulnerabilities: list[dict[str, str]]) -> dict[str, int]:
    """Count vulnerabilities by severity level.

    Args:
        vulnerabilities: List of vulnerability dicts.

    Returns:
        Dict mapping severity to count.
    """
    counts: dict[str, int] = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
        "UNKNOWN": 0,
    }

    for vuln in vulnerabilities:
        severity = vuln.get("severity", "UNKNOWN")
        if severity in counts:
            counts[severity] += 1
        else:
            counts["UNKNOWN"] += 1

    return counts


def build_docker_image(
    dockerfile_path: str | Path = "Dockerfile",
    image_name: str = DEFAULT_IMAGE_NAME,
    context_dir: str | Path = ".",
) -> bool:
    """Build a Docker image for Trivy scanning.

    Args:
        dockerfile_path: Path to the Dockerfile.
        image_name: Name/tag for the built image.
        context_dir: Docker build context directory.

    Returns:
        True if build succeeded, False otherwise.
    """
    dockerfile = Path(dockerfile_path)
    if not dockerfile.exists():
        logger.error("Dockerfile not found: %s", dockerfile)
        return False

    cmd = [
        "docker", "build",
        "-t", image_name,
        "-f", str(dockerfile),
        str(context_dir),
    ]

    logger.info("Building Docker image: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Docker image built successfully: %s", image_name)
            return True
        else:
            logger.error("Docker build failed:\n%s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("Docker build timed out after 300 seconds")
        return False
    except FileNotFoundError:
        logger.error("docker command not found")
        return False


def _is_trivy_available() -> bool:
    """Check if Trivy CLI is available in the environment."""
    return shutil.which("trivy") is not None


def get_trivy_version() -> Optional[str]:
    """Get the installed Trivy version.

    Returns:
        Version string (e.g., "0.50.0") or None if not installed.
    """
    try:
        result = subprocess.run(
            ["trivy", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Output format: "Version: 0.50.0"
            for line in result.stdout.split("\n"):
                if line.startswith("Version:"):
                    return line.split(":")[1].strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _build_error_result(error_msg: str) -> dict[str, Any]:
    """Build a result dict for an error scenario."""
    return {
        "scan_type": "error",
        "vulnerabilities": [],
        "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
        "total_vulnerabilities": 0,
        "has_critical_high": False,
        "security_passed": True,
        "error": error_msg,
    }


def _build_timeout_result(timeout: int) -> dict[str, Any]:
    """Build a result dict for a timeout scenario."""
    return {
        "scan_type": "timeout",
        "vulnerabilities": [],
        "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
        "total_vulnerabilities": 0,
        "has_critical_high": False,
        "security_passed": True,
        "error": f"Trivy scan timed out after {timeout} seconds",
    }


def _build_empty_result(scan_type: str, **kwargs) -> dict[str, Any]:
    """Build a result dict for an empty scan (no vulnerabilities)."""
    return {
        "scan_type": scan_type,
        "vulnerabilities": [],
        "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
        "total_vulnerabilities": 0,
        "has_critical_high": False,
        "security_passed": True,
        **kwargs,
    }
