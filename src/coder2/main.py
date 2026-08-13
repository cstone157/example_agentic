import os
import logging
from pathlib import Path

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph, END        # Core components of LangGraph

from agents import _init_agents_, planner_agent, router_agent, task_agent, router_logic
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
# Create the LLM instance using the specified model, base URL, and API key
# ---------------------------------------------------------------------------
llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url=BASE_URL,
    api_key=API_KEY,
    temperature=0.3,
    max_tokens=4096,
)
_init_agents_(llm)


# ---------------------------------------------------------------------------
# Define the workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(CoderAgentState)
workflow.add_node("router_agent", router_agent)
workflow.add_node("planner_agent", planner_agent)
workflow.add_node("task_agent", task_agent)


workflow.add_edge(START, "router_agent")
workflow.add_conditional_edges("router_agent", router_logic)
workflow.add_edge("planner_agent", END)
workflow.add_edge("task_agent", END)

app = workflow.compile()

# Print the ASCII representation of the graph for debugging purposes
print(app.get_graph().draw_ascii())

# Run the graph
result = app.invoke({})
print(result)