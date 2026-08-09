"""LangGraph application planner powered by a local LLM on a Spark DGX.

The workflow:
  1. Prompt the user to describe the application they want built.
  2. Send the description to the LLM using the Planning Agent instructions.
  3. Display the generated plan and save it to tmp/PLAN.md.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from coder.utils import print_and_save_md, load_file
from coder.plan import PlannerState, plan_node, PLANNER_SYSTEM_PROMPT, generate_plan

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
# Graph construction
# ---------------------------------------------------------------------------

workflow = StateGraph(PlannerState)
workflow.add_node("plan", plan_node)
workflow.set_entry_point("plan")
workflow.add_edge("plan", END)
graph = workflow.compile()



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

    # Check for an existing plan
    existing_plan = load_file("PLAN.md")
    if existing_plan:
        print()
        print("=" * 60)
        print("EXISTING PLAN FOUND")
        print(existing_plan)
        print("=" * 60)
        response = input("Would you like to continue from the existing plan? (yes/no): ").strip().lower()
        if response in ("yes", "y"):
            print("\nContinuing from existing plan...")
            # Use the existing plan text with the new description context
            initial_state: PlannerState = {
                "user_description": description,
                "plan": existing_plan,
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            # Continue from existing plan by invoking revision loop
            llm = ChatOpenAI(
                model=MODEL_NAME,
                base_url=BASE_URL,
                api_key=API_KEY,
                temperature=0.3,
                max_tokens=4096,
            )
            conversation_history: list = [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Describe the application I want built:\n\n{description}"
                ),
                AIMessage(content=existing_plan),
            ]
            plan_text = existing_plan
            # Enter revision loop
            while True:
                print_and_save_md(plan_text, "plan", "PLAN.md")

                print()
                revision = input("Would you like to revise the plan? (yes/no/exit/continue): ").strip().lower()

                if revision in ("exit", "no"):
                    print("\nDone. Final plan saved.")
                    break

                if revision == "continue":
                    print("\nProceeding with the current plan.")
                    break

                revision_text = input("Enter your revisions:\n> ").strip()
                if not revision_text:
                    print("No revisions provided. Keeping the current plan.")
                    continue

                conversation_history.append(HumanMessage(content=f"Please revise the plan based on the following feedback:\n\n{revision_text}"))
                response = llm.invoke(conversation_history)
                plan_text = response.content
                conversation_history.append(AIMessage(content=plan_text))
        else:
            print("\nGenerating a new plan...")
            generate_plan(user_description=description, graph=graph)
    else:
        generate_plan(user_description=description, graph=graph)
