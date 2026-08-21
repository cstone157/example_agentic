import logging
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agents.Coder import planner_agent
from state.CodingState import CodingState

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
# Create the LLM instance
# ---------------------------------------------------------------------------
_llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url=BASE_URL,
    api_key=API_KEY,
    temperature=0.3,
    max_tokens=4096,
)


def _planner_node(state: CodingState) -> CodingState:
    """Wrapper so planner_agent (which takes state + llm) fits LangGraph's
    single-argument node signature.

    After the user accepts the plan, prompts for an output directory and writes
    the plan file there.
    """
    state = planner_agent(state, _llm)

    # --- Plan accepted: ask where to save it --------------------------------
    default_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir = input(
        f"\nEnter directory to save the plan (default: {default_dir}): "
    ).strip()

    if not output_dir:
        output_dir = str(default_dir)

    state["output_dir"] = output_dir

    # Write the accepted plan to disk
    plan_path = Path(output_dir) / "plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(state["plan"], encoding="utf-8")

    logger.info("Plan saved to %s", plan_path)
    print(f"\nPlan written to: {plan_path}")

    return state


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
    workflow.add_node("planner", _planner_node)

    # Define edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", END)

    return workflow


def get_app():
    """Return a compiled LangGraph application ready to invoke."""
    workflow = create_workflow()
    return workflow.compile()
