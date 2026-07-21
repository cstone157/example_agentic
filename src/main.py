"""CLI Entry Point for the Multi-Agent Development Workflow.

Usage:
    python -m src.main
    python src/main.py

This script provides an interactive command-line interface for running
the LangGraph multi-agent workflow from planning through deployment.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow.graph import app_graph, get_workflow_summary
from src.workflow.state import AppWorkflowState

logger = logging.getLogger(__name__)


def print_banner() -> None:
    """Print the application banner."""
    print("=" * 70)
    print("  Multi-Agent Development Workflow")
    print("  LangGraph | Planner → Tasker → Coder → Tester → Security")
    print("=" * 70)
    print()


def print_workflow_summary() -> None:
    """Print a summary of the workflow structure."""
    summary = get_workflow_summary()
    print("\nWorkflow Structure:")
    print(f"  Name: {summary['name']}")
    print(f"  Nodes: {', '.join(summary['nodes'])}")
    print(f"  Description: {summary['description']}")
    print()


def get_app_description() -> str:
    """Prompt the user for an application description.

    Supports both interactive input and piped input (for automation).

    Returns:
        The application description string.
    """
    # Check if input is being piped
    if not sys.stdin.isatty():
        # Read from stdin for non-interactive use
        app_description = sys.stdin.read().strip()
        if app_description:
            return app_description

    # Interactive mode
    print("Enter your application description:")
    print("(Type your description and press Enter, or Ctrl+D to submit)\n")

    lines = []
    try:
        while True:
            line = input()
            if line.strip():
                lines.append(line)
            else:
                # Empty line signals end of input
                break
    except EOFError:
        pass

    return "\n".join(lines).strip()


def format_output(result: dict[str, object]) -> str:
    """Format the workflow result for display.

    Args:
        result: The final workflow state dictionary.

    Returns:
        Formatted string representation of the results.
    """
    output = []

    # Implementation Plan
    plan = result.get("implementation_plan", "")
    if plan:
        output.append("\n" + "=" * 70)
        output.append("  IMPLEMENTATION PLAN")
        output.append("=" * 70)
        output.append(plan[:2000] + "..." if len(str(plan)) > 2000 else plan)

    # User Stories
    user_stories = result.get("user_stories", [])
    if user_stories:
        output.append("\n" + "=" * 70)
        output.append("  USER STORIES")
        output.append("=" * 70)
        for i, story in enumerate(user_stories, 1):
            output.append(f"  {i}. {story}")

    # Tech Stack
    tech_stack = result.get("tech_stack", {})
    if tech_stack:
        output.append("\n" + "=" * 70)
        output.append("  TECH STACK")
        output.append("=" * 70)
        for framework, version in tech_stack.items():
            output.append(f"  - {framework}: {version}")

    # Tasks
    tasks = result.get("tasks", [])
    if tasks:
        output.append("\n" + "=" * 70)
        output.append("  TASKS")
        output.append("=" * 70)
        for task in tasks:
            priority = task.get("priority", "?")
            description = task.get("description", "")
            status = task.get("status", "pending")
            output.append(f"  [{priority}] {description} ({status})")

    # Generated Code Files
    files_written = result.get("code_files_written", [])
    if files_written:
        output.append("\n" + "=" * 70)
        output.append("  GENERATED CODE FILES")
        output.append("=" * 70)
        for filepath in files_written:
            output.append(f"  ✓ {filepath}")

    # Test Results
    tests_passed = result.get("tests_passed", False)
    test_results = result.get("test_results", {})
    if test_results:
        output.append("\n" + "=" * 70)
        output.append("  TEST RESULTS")
        output.append("=" * 70)
        output.append(f"  Passed: {test_results.get('passed', 0)}")
        output.append(f"  Failed: {test_results.get('failed', 0)}")
        output.append(f"  Errors: {test_results.get('errors', 0)}")
        output.append(f"  Skipped: {test_results.get('skipped', 0)}")
        output.append(f"  Duration: {test_results.get('duration', 0):.2f}s")
        output.append(f"  Summary: {test_results.get('summary', 'N/A')}")
        output.append(f"  Status: {'✓ PASSED' if tests_passed else '✗ FAILED'}")

    # Security Results
    vulnerabilities = result.get("vulnerabilities_found", [])
    security_passed = result.get("security_passed", False)
    if vulnerabilities or security_passed is not None:
        output.append("\n" + "=" * 70)
        output.append("  SECURITY SCAN RESULTS")
        output.append("=" * 70)
        output.append(f"  Vulnerabilities Found: {len(vulnerabilities)}")
        output.append(f"  Security Passed: {'✓ YES' if security_passed else '✗ NO'}")

        if vulnerabilities:
            output.append("\n  Vulnerability Details:")
            for vuln in vulnerabilities[:10]:  # Limit to first 10
                severity = vuln.get("severity", "UNKNOWN")
                pkg = vuln.get("package", "")
                vid = vuln.get("id", "")
                output.append(f"    [{severity}] {vid} - {pkg}")

            if len(vulnerabilities) > 10:
                output.append(f"    ... and {len(vulnerabilities) - 10} more")

    # Final Status
    status = result.get("status", "unknown")
    errors = result.get("errors", [])
    output.append("\n" + "=" * 70)
    output.append("  WORKFLOW STATUS")
    output.append("=" * 70)
    output.append(f"  Final Status: {status.upper()}")

    if errors:
        output.append("\n  Errors:")
        for error in errors:
            output.append(f"    - {error}")

    return "\n".join(output)


def run_workflow(app_description: str, verbose: bool = False, log_file: Optional[str] = None) -> dict[str, object]:
    """Run the multi-agent workflow with the given application description.

    Args:
        app_description: Description of the application to build.
        verbose: Enable verbose logging output.
        log_file: Path to write workflow log output. If None, logs to console only.

    Returns:
        The final workflow state dictionary.
    """
    # Configure logging — write to both console and file if specified
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
        logger.info("Logging to file: %s", log_path)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=datefmt,
        handlers=handlers,
    )

    logger.info("Starting workflow with app description: %s", app_description[:100])

    # Build initial state
    initial_state: AppWorkflowState = {
        "app_description": app_description,
        "messages": [{"role": "user", "content": app_description}],
        "status": "planning",
        # Initialize optional fields with defaults
        "implementation_plan": "",
        "user_stories": [],
        "tech_stack": {},
        "tasks": [],
        "generated_code": {},
        "code_files_written": [],
        "test_suite": {},
        "test_results": {},
        "tests_passed": False,
        "trivy_report": {},
        "vulnerabilities_found": [],
        "security_passed": False,
        "errors": [],
    }

    # Run the workflow
    try:
        result = app_graph.invoke(initial_state)
        logger.info("Workflow completed with status: %s", result.get("status"))
        return result

    except Exception as exc:
        logger.exception("Workflow failed with error: %s", exc)
        raise


def check_auth_credentials(args: argparse.Namespace) -> None:
    """Validate that authentication credentials are available before starting.

    Checks for any of the following authentication methods:
    - api_key argument
    - workload_identity argument
    - admin_api_key argument
    - OPENAI_API_KEY environment variable
    - OPENAI_ADMIN_KEY environment variable

    Args:
        args: Parsed command-line arguments.

    Raises:
        SystemExit: If no valid authentication method is found.
    """
    has_credentials = (
        getattr(args, "api_key", None)
        or getattr(args, "workload_identity", None)
        or getattr(args, "admin_api_key", None)
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_ADMIN_KEY")
    )

    if not has_credentials:
        print("\nError: No authentication credentials provided.")
        print("\nPlease provide one of the following:")
        print("  --api-key <key>              Your API key")
        print("  --workload-identity <id>     Workload identity identifier")
        print("  --admin-api-key <key>        Admin API key")
        print("  export OPENAI_API_KEY=<key>  Set environment variable")
        print("  export OPENAI_ADMIN_KEY=<key> Set admin environment variable")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Development Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                          # Interactive mode
  echo "Build a todo app" | python -m src.main  # Piped input
  python -m src.main --log workflow.log       # Log to file
  python -m src.main --verbose                # Verbose output
        """,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "-l", "--log",
        metavar="FILE",
        help="Write workflow log to specified file",
    )
    parser.add_argument(
        "-d", "--description",
        metavar="TEXT",
        help="Application description (alternative to interactive/piped input)",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="API key for authentication",
    )
    parser.add_argument(
        "--workload-identity",
        metavar="ID",
        help="Workload identity identifier",
    )
    parser.add_argument(
        "--admin-api-key",
        metavar="KEY",
        help="Admin API key for authentication",
    )
    parser.add_argument(
        "--base-url",
        metavar="URL",
        help="Custom API endpoint URL (for local models like Ollama, LM Studio)",
    )
    parser.add_argument(
        "--local-model",
        metavar="MODEL",
        help="Model name for local inference (e.g., llama3.2, mistral)",
    )

    args = parser.parse_args()

    # Set environment variables for local model configuration if provided
    if args.base_url:
        os.environ["OPENAI_BASE_URL"] = args.base_url
    if args.local_model:
        os.environ["OPENAI_MODEL"] = args.local_model

    # Check for authentication credentials before proceeding
    check_auth_credentials(args)

    print_banner()
    print_workflow_summary()

    # Get application description
    if args.description:
        app_description = args.description
    else:
        app_description = get_app_description()

    if not app_description:
        print("\nError: No application description provided.")
        sys.exit(1)

    print(f"\nProcessing: {app_description[:100]}...")
    print("Running multi-agent workflow...\n")

    # Run the workflow
    try:
        result = run_workflow(app_description, verbose=args.verbose, log_file=args.log)

        # Display results
        output = format_output(result)
        print(output)

        # Also save results to JSON file
        output_file = PROJECT_ROOT / "workflow_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: Workflow failed - {exc}")
        logger.exception("Workflow error")
        sys.exit(1)


if __name__ == "__main__":
    main()
