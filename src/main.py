"""LangGraph application planner powered by a local LLM on a Spark DGX.

The workflow:
  1. Prompt the user to describe the application they want built.
  2. Send the description to the LLM using the Planning Agent instructions.
  3. Display the generated plan and save it to tmp/PLAN.md.
"""

import os
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

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
# Planning agent system prompt (loaded from agents/planner/agents.md)
# ---------------------------------------------------------------------------
_PLANNER_AGENT_PATH = Path(__file__).resolve().parent.parent / "agents" / "planner" / "agents.md"
if _PLANNER_AGENT_PATH.exists():
    with open(_PLANNER_AGENT_PATH, encoding="utf-8") as _f:
        PLANNER_SYSTEM_PROMPT = _f.read()
else:
    PLANNER_SYSTEM_PROMPT = (
        "You are an expert software planning agent. Translate the user's program "
        "description into a clear, actionable development plan with file structure, "
        "task list, dependencies, and configuration."
    )

# ---------------------------------------------------------------------------
# LangGraph state definition
# ---------------------------------------------------------------------------


class PlannerState(TypedDict):
    """The state carried through the planning graph.

    Attributes:
        user_description: The application description provided by the user.
        plan: The generated development plan (output of the LLM).
        temperature: Sampling temperature for the LLM.
        max_tokens: Maximum tokens in the response.
    """

    user_description: str
    plan: str
    temperature: float
    max_tokens: int


# ---------------------------------------------------------------------------
# Planning node
# ---------------------------------------------------------------------------


def plan_node(state: PlannerState) -> PlannerState:
    """Call the LLM with the planning agent prompt and return the generated plan.

    Args:
        state: Current graph state containing the user's description,
            temperature, and max_tokens.

    Returns:
        Updated state with the generated plan stored in 'plan'.
    """
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=state.get("temperature", 0.3),
        max_tokens=state.get("max_tokens", 4096),
    )

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Describe the application I want built:\n\n{state['user_description']}"
            )
        ),
    ]

    response = llm.invoke(messages)
    return {"plan": response.content}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

workflow = StateGraph(PlannerState)
workflow.add_node("plan", plan_node)
workflow.set_entry_point("plan")
workflow.add_edge("plan", END)
graph = workflow.compile()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def generate_plan(
    user_description: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> None:
    """Generate a development plan from the user's application description.

    Interactively asks the user if they want to revise the plan after each
    generation. Revisions are submitted back to the LLM which updates the
    plan accordingly. The loop continues until the user enters 'exit' or
    'continue'.

    Args:
        user_description: The application description provided by the user.
        temperature: Sampling temperature for the LLM (lower for more deterministic plans).
        max_tokens: Maximum tokens in the response.
    """
    # Build the initial plan
    initial_state: PlannerState = {
        "user_description": user_description,
        "plan": "",
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    result = graph.invoke(initial_state)
    plan_text = result["plan"]
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Conversation history for revision turns
    conversation_history: list = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Describe the application I want built:\n\n{user_description}"
        ),
        AIMessage(content=plan_text),
    ]

    while True:
        # Display the current plan
        print("=" * 60)
        print("GENERATED DEVELOPMENT PLAN")
        print("=" * 60)
        print(plan_text)
        print("=" * 60)

        # Save to tmp/PLAN.md
        tmp_dir = Path(__file__).resolve().parent.parent / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        plan_path = tmp_dir / "PLAN.md"
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_text)
        print(f"\nPlan saved to {plan_path}")

        # Ask the user if they want to revise
        print()
        revision = input("Would you like to revise the plan? (yes/no/exit/continue): ").strip().lower()

        if revision in ("exit", "no"):
            print("\nDone. Final plan saved.")
            break

        if revision == "continue":
            print("\nProceeding with the current plan.")
            break

        # If 'yes' or anything else, treat as a revision request
        revision_text = input("Enter your revisions:\n> ").strip()
        if not revision_text:
            print("No revisions provided. Keeping the current plan.")
            continue

        # Submit revisions to the LLM
        conversation_history.append(HumanMessage(content=f"Please revise the plan based on the following feedback:\n\n{revision_text}"))
        response = llm.invoke(conversation_history)
        plan_text = response.content
        conversation_history.append(AIMessage(content=plan_text))


if __name__ == "__main__":
    # If a description is provided as a CLI argument, use it directly.
    # Otherwise, prompt the user interactively.
    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
    else:
        print("Describe the application you want built:")
        print("(Type your description and press Enter.)")
        print()
        description = input("> ").strip()

    if not description:
        print("Error: No application description provided.")
        sys.exit(1)

    generate_plan(user_description=description)
