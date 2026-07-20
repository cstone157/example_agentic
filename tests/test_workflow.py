"""Workflow Integration Tests.

Tests for the multi-agent LangGraph workflow, covering:
- State schema validation
- Graph compilation and structure
- Node execution (mocked LLM calls)
- Conditional edge routing
- Tool integration (file_ops, test_runner, trivy_scanner)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_app_description() -> str:
    """Sample application description for testing."""
    return "Build a simple REST API for managing a todo list with CRUD operations."


@pytest.fixture
def minimal_state(sample_app_description: str) -> dict[str, Any]:
    """Create a minimal workflow state for testing."""
    return {
        "app_description": sample_app_description,
        "messages": [{"role": "user", "content": sample_app_description}],
        "status": "planning",
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


@pytest.fixture
def completed_state() -> dict[str, Any]:
    """Create a fully populated workflow state for testing."""
    return {
        "app_description": "Test app",
        "messages": [{"role": "user", "content": "Test app"}],
        "status": "complete",
        "implementation_plan": "Build a todo API using FastAPI and SQLite.",
        "user_stories": [
            "As a user, I want to create todos",
            "As a user, I want to view my todos",
        ],
        "tech_stack": {"fastapi": "0.109.0", "sqlalchemy": "2.0.25"},
        "tasks": [
            {
                "id": "task-001",
                "description": "Set up FastAPI project",
                "priority": "P0",
                "dependencies": [],
                "complexity": "S",
                "status": "pending",
            }
        ],
        "generated_code": {"main.py": "from fastapi import FastAPI"},
        "code_files_written": ["/tmp/test_main.py"],
        "test_suite": {"test_main.py": "import pytest"},
        "test_results": {
            "passed": 5,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "duration": 1.23,
            "summary": "All tests passed",
        },
        "tests_passed": True,
        "trivy_report": {
            "scan_type": "image",
            "vulnerabilities": [],
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        },
        "vulnerabilities_found": [],
        "security_passed": True,
        "errors": [],
    }


# ── State Schema Tests ───────────────────────────────────────────────

class TestStateSchema:
    """Tests for the AppWorkflowState TypedDict."""

    def test_state_has_required_fields(self):
        """Verify all required state fields exist."""
        from src.workflow.state import AppWorkflowState

        required_fields = [
            "app_description",
            "implementation_plan",
            "user_stories",
            "tech_stack",
            "tasks",
            "generated_code",
            "code_files_written",
            "test_suite",
            "test_results",
            "tests_passed",
            "trivy_report",
            "vulnerabilities_found",
            "security_passed",
            "status",
            "errors",
        ]

        for field in required_fields:
            assert field in AppWorkflowState.__annotations__, (
                f"Missing field: {field}"
            )

    def test_state_type_annotations(self):
        """Verify type annotations are correct."""
        from src.workflow.state import AppWorkflowState

        annotations = AppWorkflowState.__annotations__
        assert annotations["app_description"] == str
        assert annotations["user_stories"] == list[str]
        assert annotations["tech_stack"] == dict[str, str]
        assert annotations["tasks"] == list[dict[str, str]]
        assert annotations["tests_passed"] == bool
        assert annotations["security_passed"] == bool
        assert annotations["status"] == str
        assert annotations["errors"] == list[str]


# ── Graph Compilation Tests ──────────────────────────────────────────

class TestGraphCompilation:
    """Tests for LangGraph workflow compilation."""

    def test_graph_compiles_successfully(self):
        """Verify the graph compiles without errors."""
        from src.workflow.graph import build_graph

        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        """Verify all expected nodes are registered."""
        from src.workflow.graph import app_graph

        node_names = list(app_graph.nodes.keys())
        expected_nodes = ["planner", "tasker", "coder", "tester", "security"]

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    def test_graph_has_conditional_edges(self):
        """Verify conditional edges are configured."""
        from src.workflow.graph import app_graph

        # Check that the graph has conditional routing
        transitions = app_graph.get_transitions()
        assert len(transitions) > 0

    def test_workflow_summary(self):
        """Verify workflow summary is correct."""
        from src.workflow.graph import get_workflow_summary

        summary = get_workflow_summary()
        assert summary["name"] == "Multi-Agent Development Workflow"
        assert len(summary["nodes"]) == 5
        assert len(summary["edges"]) > 0


# ── Node Execution Tests (Mocked) ────────────────────────────────────

class TestNodeExecution:
    """Tests for individual node execution with mocked LLM calls."""

    def test_run_planner_success(self, minimal_state):
        """Test planner node returns expected state updates."""
        from src.workflow.nodes import run_planner

        # Mock the LLM client
        mock_response = {
            "implementation_plan": "Use FastAPI with SQLite",
            "user_stories": ["As a user, I want to create todos"],
            "tech_stack": {"fastapi": "0.109.0"},
        }

        with patch(
            "src.workflow.nodes.call_llm_agent", return_value=mock_response
        ):
            result = run_planner(minimal_state)

        assert result["status"] == "drafting"
        assert result["implementation_plan"] == "Use FastAPI with SQLite"
        assert result["user_stories"] == ["As a user, I want to create todos"]
        assert result["tech_stack"] == {"fastapi": "0.109.0"}

    def test_run_planner_empty_input(self, minimal_state):
        """Test planner handles empty app description."""
        from src.workflow.nodes import run_planner

        empty_state = {**minimal_state, "app_description": ""}
        result = run_planner(empty_state)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    def test_run_tasker_success(self, minimal_state):
        """Test tasker node returns expected state updates."""
        from src.workflow.nodes import run_tasker

        # Populate implementation plan first
        minimal_state["implementation_plan"] = "Build a todo API"

        mock_response = {
            "tasks": [
                {
                    "id": "task-001",
                    "description": "Set up project",
                    "priority": "P0",
                    "dependencies": [],
                    "complexity": "S",
                    "status": "pending",
                }
            ]
        }

        with patch(
            "src.workflow.nodes.call_llm_agent", return_value=mock_response
        ):
            result = run_tasker(minimal_state)

        assert result["status"] == "coding"
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["id"] == "task-001"

    def test_run_coder_success(self, minimal_state):
        """Test coder node writes files and returns expected state."""
        from src.workflow.nodes import run_coder

        # Populate tasks
        minimal_state["tasks"] = [
            {
                "id": "task-001",
                "description": "Create main module",
                "priority": "P0",
                "dependencies": [],
                "complexity": "S",
                "status": "pending",
            }
        ]

        mock_response = {
            "generated_code": {"main.py": "from fastapi import FastAPI"},
        }

        with patch(
            "src.workflow.nodes.call_llm_agent", return_value=mock_response
        ):
            result = run_coder(minimal_state)

        assert result["status"] == "testing"
        assert "generated_code" in result
        assert len(result["code_files_written"]) > 0

    def test_run_tester_success(self, minimal_state):
        """Test tester node generates and runs tests."""
        from src.workflow.nodes import run_tester

        # Populate generated code
        minimal_state["generated_code"] = {
            "main.py": "def add(a, b): return a + b"
        }

        mock_response = {
            "test_suite": {"test_main.py": "def test_add(): assert add(1, 2) == 3"},
        }

        with patch(
            "src.workflow.nodes.call_llm_agent", return_value=mock_response
        ):
            with patch(
                "src.workflow.nodes._execute_pytest",
                return_value=(
                    {
                        "passed": 1,
                        "failed": 0,
                        "errors": 0,
                        "skipped": 0,
                        "duration": 0.5,
                        "summary": "1 passed",
                    },
                    True,
                ),
            ):
                result = run_tester(minimal_state)

        assert result["status"] == "securing"
        assert result["tests_passed"] is True

    def test_run_tester_failure(self, minimal_state):
        """Test tester node handles failed tests."""
        from src.workflow.nodes import run_tester

        # Populate generated code
        minimal_state["generated_code"] = {
            "main.py": "def add(a, b): return a + b"
        }

        mock_response = {
            "test_suite": {"test_main.py": "def test_add(): assert add(1, 2) == 3"},
        }

        with patch(
            "src.workflow.nodes.call_llm_agent", return_value=mock_response
        ):
            with patch(
                "src.workflow.nodes._execute_pytest",
                return_value=(
                    {
                        "passed": 0,
                        "failed": 1,
                        "errors": 0,
                        "skipped": 0,
                        "duration": 0.5,
                        "summary": "1 failed",
                    },
                    False,
                ),
            ):
                result = run_tester(minimal_state)

        assert result["status"] == "coding"  # Loop back to coder
        assert result["tests_passed"] is False

    def test_run_security_scanner_success(self, minimal_state):
        """Test security scanner returns expected results."""
        from src.workflow.nodes import run_security_scanner

        mock_report = {
            "scan_type": "image",
            "vulnerabilities": [],
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "security_passed": True,
        }

        with patch(
            "src.workflow.nodes._run_trivy_scan_docker",
            return_value=(mock_report, [], True),
        ):
            result = run_security_scanner(minimal_state)

        assert result["status"] == "complete"
        assert result["security_passed"] is True
        assert result["vulnerabilities_found"] == []


# ── Conditional Edge Tests ───────────────────────────────────────────

class TestConditionalEdges:
    """Tests for the should_fix_code conditional edge logic."""

    def test_should_route_to_security_when_tests_pass(self):
        """Verify routing to security when tests pass."""
        from src.workflow.nodes import should_fix_code

        state = {"tests_passed": True}
        assert should_fix_code(state) == "security"

    def test_should_route_to_coder_when_tests_fail(self):
        """Verify routing back to coder when tests fail."""
        from src.workflow.nodes import should_fix_code

        state = {"tests_passed": False}
        assert should_fix_code(state) == "coder"

    def test_should_route_to_coder_when_tests_missing(self):
        """Verify default routing to coder when tests_passed is missing."""
        from src.workflow.nodes import should_fix_code

        state = {}  # No tests_passed field
        assert should_fix_code(state) == "coder"


# ── Tool Integration Tests ───────────────────────────────────────────

class TestFileOpsIntegration:
    """Tests for file_ops.py integration."""

    def test_write_file_creates_directory(self):
        """Test that write_file creates parent directories."""
        from src.tools.file_ops import write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir" / "test.txt"
            written = write_file(target, "content", working_dir=Path(tmpdir))
            assert written.exists()
            assert written.read_text() == "content"

    def test_write_files_batch(self):
        """Test batch writing of multiple files."""
        from src.tools.file_ops import write_files

        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "file1.txt": "content1",
                "file2.txt": "content2",
            }
            written = write_files(files, working_dir=Path(tmpdir))
            assert len(written) == 2

    def test_write_file_rejects_traversal(self):
        """Test that path traversal is rejected."""
        from src.tools.file_ops import write_file

        with pytest.raises(ValueError, match="traversal"):
            write_file("../etc/passwd", "malicious")


class TestTestRunnerIntegration:
    """Tests for test_runner.py integration."""

    def test_run_pytest_with_no_tests(self):
        """Test pytest execution with no test files."""
        from src.tools.test_runner import run_pytest

        results, passed = run_pytest(test_paths=[])
        assert passed is False

    def test_discover_tests_nonexistent_dir(self):
        """Test test discovery with non-existent directory."""
        from src.tools.test_runner import discover_tests

        tests = discover_tests("/nonexistent/path")
        assert tests == []


class TestTrivyScannerIntegration:
    """Tests for trivy_scanner.py integration."""

    def test_trivy_not_available(self):
        """Test handling when Trivy CLI is not installed."""
        from src.tools.trivy_scanner import _is_trivy_available

        # This may pass or fail depending on environment
        result = _is_trivy_available()
        assert isinstance(result, bool)

    def test_build_error_result(self):
        """Test error result construction."""
        from src.tools.trivy_scanner import _build_error_result

        result = _build_error_result("test error")
        assert result["error"] == "test error"
        assert result["security_passed"] is True  # Safe default

    def test_count_by_severity(self):
        """Test severity counting."""
        from src.tools.trivy_scanner import count_by_severity

        vulns = [
            {"severity": "CRITICAL"},
            {"severity": "HIGH"},
            {"severity": "MEDIUM"},
            {"severity": "LOW"},
            {"severity": "UNKNOWN"},
        ]
        counts = count_by_severity(vulns)
        assert counts["CRITICAL"] == 1
        assert counts["HIGH"] == 1
        assert counts["MEDIUM"] == 1
        assert counts["LOW"] == 1
        assert counts["UNKNOWN"] == 1


# ── End-to-End Tests (Mocked) ───────────────────────────────────────

class TestEndToEnd:
    """Integration tests for the complete workflow with mocked LLM."""

    def test_full_workflow_pipeline(self, minimal_state):
        """Test the full workflow pipeline with mocked responses."""
        from src.workflow.nodes import (
            run_coder,
            run_planner,
            run_security_scanner,
            run_tasker,
            run_tester,
        )

        state = {**minimal_state}

        # Mock all LLM calls
        mock_responses = iter([
            # Planner response
            {
                "implementation_plan": "Build todo API with FastAPI",
                "user_stories": ["Create todos", "View todos"],
                "tech_stack": {"fastapi": "0.109.0"},
            },
            # Tasker response
            {
                "tasks": [
                    {
                        "id": "task-001",
                        "description": "Set up FastAPI",
                        "priority": "P0",
                        "dependencies": [],
                        "complexity": "S",
                        "status": "pending",
                    }
                ]
            },
            # Coder response
            {
                "generated_code": {"main.py": "from fastapi import FastAPI"},
            },
            # Tester response
            {
                "test_suite": {"test_main.py": "def test_main(): pass"},
            },
        ])

        def mock_call_llm(*args, **kwargs):
            return next(mock_responses)

        with patch("src.workflow.nodes.call_llm_agent", side_effect=mock_call_llm):
            with patch(
                "src.workflow.nodes._execute_pytest",
                return_value=(
                    {"passed": 1, "failed": 0, "errors": 0, "skipped": 0, "duration": 0.1, "summary": "1 passed"},
                    True,
                ),
            ):
                with patch(
                    "src.workflow.nodes._run_trivy_scan_docker",
                    return_value=(
                        {
                            "scan_type": "image",
                            "vulnerabilities": [],
                            "security_passed": True,
                        },
                        [],
                        True,
                    ),
                ):
                    # Run the pipeline
                    state = run_planner(state)
                    assert state["status"] == "drafting"

                    state = run_tasker(state)
                    assert state["status"] == "coding"

                    state = run_coder(state)
                    assert state["status"] == "testing"

                    state = run_tester(state)
                    assert state["status"] == "securing"

                    state = run_security_scanner(state)
                    assert state["status"] == "complete"

    def test_workflow_with_test_failure_loop(self, minimal_state):
        """Test workflow loops back to coder when tests fail."""
        from src.workflow.nodes import (
            run_coder,
            run_planner,
            run_tasker,
            run_tester,
        )

        state = {**minimal_state}

        mock_responses = iter([
            # Planner
            {
                "implementation_plan": "Build todo API",
                "user_stories": ["Create todos"],
                "tech_stack": {"fastapi": "0.109.0"},
            },
            # Tasker
            {"tasks": [{"id": "task-001", "description": "Set up", "priority": "P0", "dependencies": [], "complexity": "S", "status": "pending"}]},
            # Coder (first attempt - buggy code)
            {"generated_code": {"main.py": "def add(a, b): return a + c"}},  # Bug: 'c' undefined
        ])

        def mock_call_llm(*args, **kwargs):
            return next(mock_responses)

        with patch("src.workflow.nodes.call_llm_agent", side_effect=mock_call_llm):
            with patch(
                "src.workflow.nodes._execute_pytest",
                return_value=(
                    {"passed": 0, "failed": 1, "errors": 0, "skipped": 0, "duration": 0.1, "summary": "1 failed"},
                    False,
                ),
            ):
                state = run_planner(state)
                state = run_tasker(state)
                state = run_coder(state)

                # First test run fails
                state = run_tester(state)
                assert state["status"] == "coding"  # Loops back!


# ── CLI Tests ────────────────────────────────────────────────────────

class TestCLI:
    """Tests for the CLI entry point."""

    def test_format_output_minimal(self):
        """Test output formatting with minimal data."""
        from src.main import format_output

        result = {"status": "complete"}
        output = format_output(result)
        assert "COMPLETE" in output.upper()

    def test_format_output_with_vulnerabilities(self):
        """Test output formatting includes vulnerability details."""
        from src.main import format_output

        result = {
            "status": "complete",
            "vulnerabilities_found": [
                {"id": "CVE-2024-1234", "severity": "HIGH", "package": "requests"},
            ],
            "security_passed": False,
        }
        output = format_output(result)
        assert "CVE-2024-1234" in output
        assert "HIGH" in output

    def test_format_output_with_test_results(self):
        """Test output formatting includes test results."""
        from src.main import format_output

        result = {
            "status": "complete",
            "test_results": {
                "passed": 10,
                "failed": 2,
                "errors": 0,
                "skipped": 1,
                "duration": 5.67,
                "summary": "10 passed, 2 failed",
            },
            "tests_passed": False,
        }
        output = format_output(result)
        assert "10" in output
        assert "FAILED" in output
