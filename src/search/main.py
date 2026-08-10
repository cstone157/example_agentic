import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Switch to using the ollama LLM interface instead of OpenAI's API
# from langchain_google_genai import ChatGoogleGenerativeAI  # Google LLM interface

from crewai_tools import SerperDevTool                    # Web search tool
from langchain_community.tools import DuckDuckGoSearchRun # Web search tool
from langchain.tools import tool                          # Decorator to turn functions into tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent         # Helper to build ReAct-style agents
# from langchain.agents import create_react_agent
from langgraph.graph import START, StateGraph, END        # Core components of LangGraph
from typing import TypedDict                              # Used to define structured state

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
# Tool Definition
# ---------------------------------------------------------------------------
@tool
def serper_search(user_query: str) -> str:
    """
    Perform a real-time search using the Serper API.

    This tool takes a plain-text user query, sends it to Serper (a web search API),
    and returns a string with the top relevant results. It can be used by agents
    to gather up-to-date information from the internet as part of a reasoning or
    research task.

    Args:
        user_query (str): A natural language search prompt.

    Returns:
        str: A formatted string of search results from Serper.
    """
    # return SerperDevTool().run(query=user_query)
    return SerperDevTool().run(search_query=user_query)

# ---------------------------------------------------------------------------
# Tool Definition
# ---------------------------------------------------------------------------
@tool
def duck_search(user_query: str) -> str:
    """
    Perform a real-time search using the DuckDuckGo API.

    This tool takes a plain-text user query, sends it to DuckDuckGo (a web search API),
    and returns a string with the top relevant results. It can be used by agents
    to gather up-to-date information from the internet as part of a reasoning or
    research task.

    Args:
        user_query (str): A natural language search prompt.

    Returns:
        str: A formatted string of search results from DuckDuckGo.
    """
    return DuckDuckGoSearchRun().run(tool_input=user_query)

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

# ---------------------------------------------------------------------------
# Create a ReAct-style agent that can use the Serper search tool
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    user_query: str
    answer: str

# ---------------------------------------------------------------------------
# Define Node
# ---------------------------------------------------------------------------
def search_agent(state: AgentState) -> str:
    """
    Executes a ReAct-style agent that processes a user query.

    This function takes the current state (which includes the user's question),
    creates an agent using the Gemini language model and the `serper_search` tool,
    then runs the agent to get a response. The final answer is returned as updated state.

    Args:
        state (AgentState): A dictionary with the user's query.

    Returns:
        dict: Updated state with the generated answer.
    """
    # agent = create_react_agent(llm, [serper_search])
    agent = create_react_agent(llm, [duck_search])
    result = agent.invoke({"messages": state["user_query"]})
    return {"answer": result["messages"][-1].content}


# ---------------------------------------------------------------------------
# Math Agent
# ---------------------------------------------------------------------------
def math_agent(state: AgentState) -> str:
    """
    A math-solving agent that uses the LLM to process and solve math problems.

    Args:
        state (AgentState): Contains the user's query.

    Returns:
        dict: Updated state with the computed answer from the LLM.
    """
    print("--- Math Node ---")
    prompt = f"Solve this math problem and return only the answer: {state['user_query']}"
    response = llm.invoke(prompt)
    state['answer'] = response.content.strip()
    return state

# ---------------------------------------------------------------------------
# Router Agent
# ---------------------------------------------------------------------------
def router_agent(state: AgentState) -> str:
    """
    Captures a user query from the command line and updates the state.

    This function acts as an input node in the LangGraph workflow. It prompts the user
    to enter a query via the console, then stores that input in the shared state under
    the 'user_query' key, which will be used to route to the appropriate agents.

    Args:
        state (AgentState): The current state dictionary (can be empty or partially filled).

    Returns:
        dict: Updated state containing the user's query.
    """
    print("--- Input Node ---")
    state['user_query'] = input("Input user query: ")
    return state

from typing import Literal

# ---------------------------------------------------------------------------
# Secify the routing logic to choose between the math agent and search agent
# ---------------------------------------------------------------------------
agent_docs = {
    "search_agent": search_agent.__doc__,
    "math_agent": math_agent.__doc__
}

# ---------------------------------------------------------------------------
# Define the routing logic function that uses the LLM to decide which agent to invoke
# ---------------------------------------------------------------------------
def routing_logic(state: AgentState) -> Literal["math_agent", "search_agent"]:
    """
    Uses the LLM to choose between 'math_agent' and 'search_agent'
    based on the intent of the user query and the agents' docstrings.

    Args:
        state (AgentState): The current state containing the user query.

    Returns:
        str: The name of the next node to route to.
    """
    prompt = f"""
    You are a router agent. Your task is to choose the best agent for the job.
    Here is the user query: {state['user_query']}

    You can choose from the following agents:
    - math_agent: {agent_docs['math_agent']}
    - search_agent: {agent_docs['search_agent']}

    Which agent should handle this query? Respond with just the agent name.
    """
    response = llm.invoke(prompt)
    decision = response.content.strip().lower()
    return "math_agent" if "math" in decision else "search_agent"

# ---------------------------------------------------------------------------
# Define Graph 
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)
# workflow.add_node("search_agent", search_agent)
# workflow.add_edge(START, "search_agent")
# workflow.add_edge("search_agent", END)

workflow.add_node("router_agent", router_agent) # Adds the new router agent to the flow
workflow.add_node("search_agent", search_agent)
workflow.add_node("math_agent", math_agent) # Adds the math agent to the flow

workflow.add_edge(START, "router_agent")
workflow.add_conditional_edges("router_agent", routing_logic)
workflow.add_edge("search_agent", END)
workflow.add_edge("math_agent", END)

app = workflow.compile()

# from IPython.display import Image, display
# Image(app.get_graph().draw_mermaid_png())
print(app.get_graph().draw_ascii())

# --- Run Graph ---
# result = app.invoke({"user_query": "Who won the IPL 2025 final?"})
result = app.invoke({})
print(result["answer"])