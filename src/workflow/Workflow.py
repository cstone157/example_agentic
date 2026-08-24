import logging
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agents.Planer import planner_agent
from agents.Tasker import tasker_agent
from state.CodingState import CodingState

logger = logging.getLogger(__name__)

def create_workflow() -> StateGraph:
    """Build and return a compiled LangGraph StateGraph for the coding workflow.

    Workflow:
        START → planner_agent (loops internally until user accepts plan)
        planner_agent → END

    The planner_agent handles its own acceptance loop, so the graph itself
    has no conditional edges — once the user approves the plan the node
    returns and the workflow completes.
    """
    workflow = StateGraph(CodingState)

    # Register nodes
    workflow.add_node("planner", planner_agent)
    workflow.add_node("tasker", tasker_agent)

    # Define edges
    workflow.add_edge(START, "planner")
    # workflow.add_edge("planner", "tasker")
    # workflow.add_edge("tasker", END)
    workflow.add_edge("planner", END)

    return workflow


def get_app():
    """Return a compiled LangGraph application ready to invoke."""
    workflow = create_workflow()
    return workflow.compile()
