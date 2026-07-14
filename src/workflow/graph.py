from langgraph.graph import StateGraph, START, END
from src.workflow.state import AppWorkflowState
from src.workflow.nodes import (
    run_planner,
    run_tasker,
    run_coder,
    run_tester,
    run_security_scanner,
)

# Build the graph
workflow = StateGraph(AppWorkflowState)

# Add nodes
workflow.add_node("planner", run_planner)
workflow.add_node("tasker", run_tasker)
workflow.add_node("coder", run_coder)
workflow.add_node("tester", run_tester)
workflow.add_node("security", run_security_scanner)

# Define edges (linear with conditional branches)
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "tasker")
workflow.add_edge("tasker", "coder")
workflow.add_edge("coder", "tester")

# Conditional: if tests fail → loop back to coder for fixes
workflow.add_conditional_edges(
    "tester",
    should_fix_code,       # returns "coder" or "security"
    {"coder": "coder", "security": "security"}
)

workflow.add_edge("security", END)

# Compile the graph
app_graph = workflow.compile()