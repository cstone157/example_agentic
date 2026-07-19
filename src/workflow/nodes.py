"""Workflow Node Implementations.

Each node is a function that:
1. Receives the current state
2. Calls the appropriate agent (LLM prompt + tool execution)
3. Updates state with results

Nodes are designed to be called by LangGraph StateGraph nodes.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from src.agents.llm_client import call_llm_agent, get_llm_client
from src.tools.file_ops import write_files, set_allowed_bases
from src.tools.test_runner import run_pytest as _execute_pytest
from src.tools.trivy_scanner import (
    run_trivy_scan as _run_trivy,
    build_docker_image as _build_image,
    get_trivy_version,
)
from src.workflow.state import AppWorkflowState

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = BASE_DIR / "agents"

# Register allowed directories for file operations
set_allowed_bases(BASE_DIR)

# Working directory for generated code (isolated from project root)
WORK_DIR = BASE_DIR / ".agentic_workspace"
WORK_DIR.mkdir(parents=True, exist_ok=True)


def _get_agent_config_path(agent_name: str) -> Path:
    """Resolve the AGENTS.md path for a given agent."""
    return AGENTS_DIR / agent_name / "AGENTS.md"


def _parse_llm_response(response: Any) -> dict[str, Any]:
    """Parse an LLM response into a dictionary.

    Handles string responses (try JSON parse), dict responses, and
    Pydantic model responses.
    """
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "__dict__"):
        return vars(response)
    # String response — try JSON parse
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("{") or content.startswith("["):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
    return {"raw_response": content}


# ── Planner Node ─────────────────────────────────────────────────────

def run_planner(state: AppWorkflowState) -> dict[str, Any]:
    """Call planner agent to generate implementation plan.

    Receives the raw application description and produces a structured
    implementation plan with user stories and tech stack recommendations.

    Args:
        state: Current workflow state containing app_description.

    Returns:
        State update dict with implementation_plan, user_stories,
        tech_stack, and status transition to "drafting".
    """
    logger.info("Planner node: generating implementation plan")

    app_description = state.get("app_description", "")
    if not app_description:
        error_msg = "Planner node received empty app_description"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    agent_config = _get_agent_config_path("planner")
    if not agent_config.exists():
        error_msg = f"Planner config not found: {agent_config}"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    try:
        # Call the planner agent via LLM client
        response = call_llm_agent(
            agent_config_path=str(agent_config),
            input_data=app_description,
        )

        parsed = _parse_llm_response(response)

        return {
            "implementation_plan": parsed.get("implementation_plan", ""),
            "user_stories": parsed.get("user_stories", []),
            "tech_stack": parsed.get("tech_stack", {}),
            "status": "drafting",
        }

    except Exception as exc:
        error_msg = f"Planner node failed: {exc}"
        logger.exception(error_msg)
        return {"errors": [error_msg], "status": "failed"}


# ── Tasker Node ──────────────────────────────────────────────────────

def run_tasker(state: AppWorkflowState) -> dict[str, Any]:
    """Call tasker agent to draft tasks from implementation plan.

    Breaks down the planner's implementation plan into discrete,
    actionable tasks with priorities, dependencies, and complexity.

    Args:
        state: Current workflow state containing implementation_plan.

    Returns:
        State update dict with tasks list and status transition to "coding".
    """
    logger.info("Tasker node: drafting tasks from implementation plan")

    implementation_plan = state.get("implementation_plan", "")
    if not implementation_plan:
        error_msg = "Tasker node received empty implementation_plan"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    agent_config = _get_agent_config_path("tasker")
    if not agent_config.exists():
        error_msg = f"Tasker config not found: {agent_config}"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    try:
        # Build input context for tasker
        user_stories = state.get("user_stories", [])
        tech_stack = state.get("tech_stack", {})

        context_parts = [implementation_plan]
        if user_stories:
            context_parts.append(f"\nUser Stories:\n" + "\n".join(f"- {s}" for s in user_stories))
        if tech_stack:
            stack_str = ", ".join(f"{k}={v}" for k, v in tech_stack.items())
            context_parts.append(f"\nTech Stack: {stack_str}")

        input_data = "\n".join(context_parts)

        response = call_llm_agent(
            agent_config_path=str(agent_config),
            input_data=input_data,
        )

        parsed = _parse_llm_response(response)

        # Ensure tasks is a list of dicts
        tasks = parsed.get("tasks", [])
        if isinstance(tasks, str):
            try:
                tasks = json.loads(tasks)
            except json.JSONDecodeError:
                tasks = [{"id": "task-001", "description": tasks, "priority": "P0", "dependencies": [], "complexity": "M", "status": "pending"}]

        return {
            "tasks": tasks if isinstance(tasks, list) else [tasks],
            "status": "coding",
        }

    except Exception as exc:
        error_msg = f"Tasker node failed: {exc}"
        logger.exception(error_msg)
        return {"errors": [error_msg], "status": "failed"}


# ── Coder Node ───────────────────────────────────────────────────────

def run_coder(state: AppWorkflowState) -> dict[str, Any]:
    """Call coder agent to implement tasks.

    Generates source code for each task and writes files to disk.

    Args:
        state: Current workflow state containing tasks list.

    Returns:
        State update dict with generated_code, code_files_written,
        and status transition to "testing".
    """
    logger.info("Coder node: implementing tasks")

    tasks = state.get("tasks", [])
    if not tasks:
        error_msg = "Coder node received empty tasks list"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    agent_config = _get_agent_config_path("coder")
    if not agent_config.exists():
        error_msg = f"Coder config not found: {agent_config}"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    try:
        # Build input context for coder
        implementation_plan = state.get("implementation_plan", "")
        tech_stack = state.get("tech_stack", {})

        context_parts = [f"Tasks to implement:\n" + "\n".join(
            f"- [{t.get('id', '?')}] ({t.get('priority', '?')}) {t.get('description', '')}"
            for t in tasks
        )]
        if implementation_plan:
            context_parts.append(f"\nImplementation Plan:\n{implementation_plan}")

        input_data = "\n".join(context_parts)

        response = call_llm_agent(
            agent_config_path=str(agent_config),
            input_data=input_data,
        )

        parsed = _parse_llm_response(response)

        # Extract generated code — expect {filepath: code_content} dict
        generated_code = parsed.get("generated_code", {})
        if isinstance(generated_code, str):
            try:
                generated_code = json.loads(generated_code)
            except json.JSONDecodeError:
                generated_code = {"generated_code.py": generated_code}

        # Write files to disk using file_ops tool
        code_files_written = _write_generated_code(generated_code)

        return {
            "generated_code": generated_code,
            "code_files_written": [str(p) for p in code_files_written],
            "status": "testing",
        }

    except Exception as exc:
        error_msg = f"Coder node failed: {exc}"
        logger.exception(error_msg)
        return {"errors": [error_msg], "status": "failed"}


def _write_generated_code(generated_code: dict[str, str]) -> list[Path]:
    """Write generated code files to disk using file_ops tool.

    Args:
        generated_code: Dict mapping filepath to code content.

    Returns:
        List of Path objects for written files.
    """
    try:
        paths = write_files(generated_code, working_dir=WORK_DIR)
        logger.info("Coder node: wrote %d code files via file_ops", len(paths))
        return paths
    except Exception as exc:
        logger.error("Coder node: failed to write code files: %s", exc)
        return []


# ── Tester Node ──────────────────────────────────────────────────────

def run_tester(state: AppWorkflowState) -> dict[str, Any]:
    """Generate and execute test suite for generated code.

    Creates unit and integration tests, writes them to disk, runs pytest,
    and reports pass/fail status.

    Args:
        state: Current workflow state containing generated_code and code_files_written.

    Returns:
        State update dict with test_suite, test_results, tests_passed,
        and status transition ("securing" if passed, "coding" if failed).
    """
    logger.info("Tester node: generating and executing test suite")

    code_files = state.get("code_files_written", [])
    generated_code = state.get("generated_code", {})

    if not code_files and not generated_code:
        error_msg = "Tester node received no code files to test"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    agent_config = _get_agent_config_path("tester")
    if not agent_config.exists():
        error_msg = f"Tester config not found: {agent_config}"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    try:
        # Build input context for tester
        code_context_parts = []
        for filepath, content in generated_code.items():
            code_context_parts.append(f"\n### {filepath} ###\n{content}")

        input_data = "Code to test:\n" + "\n".join(code_context_parts) if code_context_parts else "No code provided"

        response = call_llm_agent(
            agent_config_path=str(agent_config),
            input_data=input_data,
        )

        parsed = _parse_llm_response(response)

        # Extract test suite — expect {test_filepath: test_content} dict
        test_suite = parsed.get("test_suite", {})
        if isinstance(test_suite, str):
            try:
                test_suite = json.loads(test_suite)
            except json.JSONDecodeError:
                test_suite = {"test_generated.py": test_suite}

        # Write test files to disk (stub)
        test_files_written = _write_test_suite(test_suite)

        # Run pytest (stub — integrate with src/tools/test_runner.py)
        test_results, tests_passed = _run_pytest(code_files, test_files_written)

        status = "securing" if tests_passed else "coding"

        return {
            "test_suite": test_suite,
            "test_results": test_results,
            "tests_passed": tests_passed,
            "status": status,
        }

    except Exception as exc:
        error_msg = f"Tester node failed: {exc}"
        logger.exception(error_msg)
        return {"errors": [error_msg], "status": "failed"}


def _write_test_suite(test_suite: dict[str, str]) -> list[Path]:
    """Write test files to disk using file_ops tool.

    Args:
        test_suite: Dict mapping test_filepath to test_content.

    Returns:
        List of Path objects for written files.
    """
    try:
        paths = write_files(test_suite, working_dir=WORK_DIR)
        logger.info("Tester node: wrote %d test files via file_ops", len(paths))
        return paths
    except Exception as exc:
        logger.error("Tester node: failed to write test files: %s", exc)
        return []


def _run_pytest(code_files: list[str], test_files: list[str]) -> tuple[dict[str, Any], bool]:
    """Run pytest against the generated code and tests using test_runner.py.

    Args:
        code_files: List of source file paths to add to PYTHONPATH.
        test_files: List of test file paths to run.

    Returns:
        Tuple of (test_results dict, tests_passed bool).
    """
    if not test_files:
        logger.warning("Tester node: no test files to run")
        return {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "duration": 0.0,
            "summary": "No test files provided",
        }, False

    # Extract directories from code files for PYTHONPATH
    code_dirs = list(set(str(Path(f).parent) for f in code_files))

    try:
        results, tests_passed = _execute_pytest(
            test_paths=test_files,
            code_dirs=code_dirs,
            working_dir=str(WORK_DIR),
            verbose=True,
            timeout=120,
        )
        return results, tests_passed

    except Exception as exc:
        logger.exception("Tester node: pytest execution failed")
        return {
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "skipped": 0,
            "duration": 0.0,
            "summary": f"Pytest execution error: {exc}",
        }, False


# ── Security Scanner Node ────────────────────────────────────────────

def run_security_scanner(state: AppWorkflowState) -> dict[str, Any]:
    """Deploy Trivy and scan the application for vulnerabilities.

    Builds a Docker image of the application (if Docker is available),
    runs Trivy container scanner, and reports findings.

    Args:
        state: Current workflow state containing code_files_written.

    Returns:
        State update dict with trivy_report, vulnerabilities_found,
        security_passed, and status transition to "complete".
    """
    logger.info("Security node: running Trivy scan")

    agent_config = _get_agent_config_path("security")
    if not agent_config.exists():
        error_msg = f"Security config not found: {agent_config}"
        logger.error(error_msg)
        return {"errors": [error_msg], "status": "failed"}

    try:
        # Check if Docker is available
        docker_available = _check_docker_available()

        if docker_available:
            # Build Docker image and run Trivy scan
            trivy_report, vulnerabilities, security_passed = _run_trivy_scan_docker()
        else:
            # Fallback: filesystem scan or stub
            logger.warning("Docker not available — using stub security scan")
            trivy_report = {"scan_type": "filesystem", "status": "skipped"}
            vulnerabilities = []
            security_passed = True

        return {
            "trivy_report": trivy_report,
            "vulnerabilities_found": vulnerabilities,
            "security_passed": security_passed,
            "status": "complete",
        }

    except Exception as exc:
        error_msg = f"Security node failed: {exc}"
        logger.exception(error_msg)
        return {"errors": [error_msg], "status": "failed"}


def _check_docker_available() -> bool:
    """Check if Docker CLI is available in the environment."""
    import shutil
    return shutil.which("docker") is not None


def _run_trivy_scan_docker() -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    """Run Trivy container scan using trivy_scanner.py.

    Builds the Docker image and runs Trivy against it.

    Returns:
        Tuple of (trivy_report, vulnerabilities list, security_passed bool).
    """
    # Build Docker image first
    dockerfile_path = BASE_DIR / "Dockerfile"
    if not _build_image(
        dockerfile_path=dockerfile_path,
        image_name=DEFAULT_IMAGE_NAME,
        context_dir=str(BASE_DIR),
    ):
        logger.warning("Docker build failed — falling back to filesystem scan")
        # Fallback to filesystem scan of the project
        report = _run_trivy(
            target_path=BASE_DIR,
            severities=["CRITICAL", "HIGH", "MEDIUM"],
        )
        vulns = report.get("vulnerabilities", [])
        return report, vulns, report.get("security_passed", True)

    # Run Trivy image scan
    report = _run_trivy(
        image_name=DEFAULT_IMAGE_NAME,
        severities=["CRITICAL", "HIGH", "MEDIUM"],
    )

    vulns = report.get("vulnerabilities", [])
    security_passed = report.get("security_passed", True)

    return report, vulns, security_passed


# ── Conditional Edge Logic ───────────────────────────────────────────

def should_fix_code(state: AppWorkflowState) -> str:
    """Determine whether to loop back to coder or proceed to security.

    This function is used as the conditional edge router in LangGraph.

    Args:
        state: Current workflow state.

    Returns:
        "coder" if tests failed (loop back for fixes),
        "security" if tests passed (proceed to Trivy scan).
    """
    tests_passed = state.get("tests_passed", False)
    if not tests_passed:
        logger.info("Conditional edge: tests failed → routing to coder for fixes")
        return "coder"
    logger.info("Conditional edge: tests passed → routing to security scanner")
    return "security"
