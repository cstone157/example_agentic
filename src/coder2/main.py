import os
import logging
from pathlib import Path

from dotenv import load_dotenv

from langgraph.graph import START, StateGraph, END        # Core components of LangGraph

from agents import planner_agent, router_agent
from state import CoderAgentState

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load environment variables from .env file (if present)
# ---------------------------------------------------------------------------
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen3.6:35b-a3b-bf16")
API_KEY: str = os.getenv("LLM_API_KEY", "ollama")

# ---------------------------------------------------------------------------
# Define the workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(CoderAgentState)
workflow.add_node("router_agent", router_agent)
workflow.add_node("planner_agent", planner_agent)

workflow.set_entry_point("router_agent")
workflow.add_edge("router_agent", "planner_agent")
workflow.add_edge("planner_agent", END)

app = workflow.compile()

# Log the ASCII representation of the graph for debugging purposes
logger.info(app.get_graph().draw_ascii())

# Run the graph
result = app.invoke({})
print(result)