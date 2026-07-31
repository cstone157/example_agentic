"""
example_graph_01.py - LangGraph workflow that generates code based on user description.

This example demonstrates a simple LangGraph workflow that:
1. Asks the user to describe a function they want written
2. Uses the Coder Agent's AGENTS.md as system context for the LLM
3. Generates production-quality Python code following project conventions
"""

import os
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph, START


# ── Load Coder Agent context ─────────────────────────────────────────────────
AGENT_MD_PATH = Path(__file__).parent.parent / "agents" / "coder" / "AGENTS.md"

if AGENT_MD_PATH.exists():
    CODER_AGENT_CONTEXT = AGENT_MD_PATH.read_text()
else:
    CODER_AGENT_CONTEXT = (
        "You are a Python coder. Write production-quality code with type hints, "
        "docstrings, and error handling."
    )


# ── State definition ─────────────────────────────────────────────────────────
class GraphState(TypedDict):
    """State for the code-generation workflow."""

    user_description: str          # What the user wants
    agent_context: str             # Coder Agent AGENTS.md content
    system_prompt: str             # Combined system prompt for LLM
    generated_code: str            # Code produced by the LLM


# ── Node functions ───────────────────────────────────────────────────────────
def ask_user(state: GraphState) -> GraphState:
    """Prompt the user to describe a function they want written."""
    print("\n" + "=" * 60)
    print("  Code Generation Agent")
    print("=" * 60)
    description = input("\nDescribe the function you'd like me to write:\n  > ").strip()
    if not description:
        description = "A simple hello world function"
    return {"user_description": description}


def build_prompt(state: GraphState) -> GraphState:
    """Construct the system prompt from the Coder Agent context + user request."""
    system_prompt = (
        f"{CODER_AGENT_CONTEXT}\n\n"
        "## Your Task\n"
        f"Generate a Python function based on this description:\n"
        f'  "{state["user_description"]}"\n\n'
        "Follow all conventions from the Coder Agent guidelines above.\n"
        "Output ONLY the Python code — no explanations, no markdown fences."
    )
    return {"agent_context": CODER_AGENT_CONTEXT, "system_prompt": system_prompt}


def generate_code(state: GraphState) -> GraphState:
    """Call the local vLLM server to generate the function."""
    # Use the OpenAI-compatible API endpoint provided by vLLM
    llm = ChatOpenAI(
        model=os.getenv("VLLM_MODEL", "local"),  # model name doesn't matter for /v1/chat/completions
        base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
        api_key="not-needed",  # vLLM doesn't require an API key by default
        temperature=0.2,
    )

    messages = [
        {"role": "system", "content": state["system_prompt"]},
        {"role": "user", "content": f"Write the function now."},
    ]

    response = llm.invoke(messages)
    return {"generated_code": response.content}


def display_result(state: GraphState) -> GraphState:
    """Print the generated code to the user."""
    print("\n" + "=" * 60)
    print("  Generated Code")
    print("=" * 60)
    print(f"\n{state['generated_code']}\n")
    return state


# ── Build the graph ──────────────────────────────────────────────────────────
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("ask_user", ask_user)
workflow.add_node("build_prompt", build_prompt)
workflow.add_node("generate_code", generate_code)
workflow.add_node("display_result", display_result)

# Define edges: START → ask_user → build_prompt → generate_code → display_result → END
workflow.add_edge(START, "ask_user")
workflow.add_edge("ask_user", "build_prompt")
workflow.add_edge("build_prompt", "generate_code")
workflow.add_edge("generate_code", "display_result")
workflow.add_edge("display_result", END)

# Compile the graph
app = workflow.compile()


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    initial_state: GraphState = {
        "user_description": "",
        "agent_context": CODER_AGENT_CONTEXT,
        "system_prompt": "",
        "generated_code": "",
    }

    result = app.invoke(initial_state)
