"""LangGraph Workflow Graph.

Compiles the multi-agent development workflow into a LangGraph StateGraph
with conditional edges for the test-fix loop.

Workflow:
    START → planner → tasker → coder → tester → (coder | security) → END
                              ↑              │
                              └──────────────┘ (if tests fail)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.workflow.nodes import (
    run_coder,
    run_planner,
    run_security_scanner,
    run_tasker,
    run_tester,
    should_fix_code,
)
from src.workflow.state import AppWorkflowState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build and compile the multi-agent workflow graph.

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # Initialize the state graph with our custom state schema
    workflow = StateGraph(AppWorkflowState)

    # ── Add Nodes ────────────────────────────────────────────────────
    # Each node is a function that receives state and returns updates
    workflow.add_node("planner", run_planner)
    workflow.add_node("tasker", run_tasker)
    workflow.add_node("coder", run_coder)
    workflow.add_node("tester", run_tester)
    workflow.add_node("security", run_security_scanner)

    # ── Define Edges ─────────────────────────────────────────────────
    # Linear flow with conditional branching for test-fix loop

    # Start → Planner
    workflow.add_edge(START, "planner")

    # Sequential flow: planner → tasker → coder → tester
    workflow.add_edge("planner", "tasker")
    workflow.add_edge("tasker", "coder")
    workflow.add_edge("coder", "tester")

    # Conditional edge: tester → coder (if tests fail) or security (if passed)
    workflow.add_conditional_edges(
        "tester",
        should_fix_code,  # Router function returning "coder" or "security"
        {
            "coder": "coder",      # Loop back to coder for fixes
            "security": "security", # Proceed to security scan
        },
    )

    # Security → End (final stage)
    workflow.add_edge("security", END)

    # ── Compile Graph ────────────────────────────────────────────────
    app_graph = workflow.compile()

    logger.info("Compiled LangGraph with 5 nodes and conditional edges")
    return app_graph


# Export the compiled graph for direct use
app_graph = build_graph()


def get_workflow_summary() -> dict[str, Any]:
    """Get a summary of the workflow structure.

    Returns:
        Dict describing the workflow nodes, edges, and flow.
    """
    return {
        "name": "Multi-Agent Development Workflow",
        "nodes": ["planner", "tasker", "coder", "tester", "security"],
        "edges": [
            ("START", "planner"),
            ("planner", "tasker"),
            ("tasker", "coder"),
            ("coder", "tester"),
            ("tester", "coder", "conditional"),  # if tests fail
            ("tester", "security", "conditional"),  # if tests pass
            ("security", "END"),
        ],
        "description": (
            "Linear workflow with conditional test-fix loop. "
            "Tests failing routes back to coder; passing routes to security scanner."
        ),
    }
