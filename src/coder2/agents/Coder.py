import logging
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state.CodingState import CodingState

logger = logging.getLogger(__name__)

_PLANNER_SYSTEM_PROMPT_ = (
    "You are an expert software planning agent. Translate the user's program "
    "description into a clear, actionable development plan with file structure, "
    "task list, dependencies, and configuration."
)


def _load_planner_prompt() -> str:
    """Load planner prompt from agents.md if available."""
    planner_path = Path(__file__).resolve().parent.parent / "agents" / "planner" / "agents.md"
    if planner_path.exists():
        with open(planner_path, encoding="utf-8") as f:
            return f.read()
    return _PLANNER_SYSTEM_PROMPT_


def planner_agent(state: CodingState, llm: ChatOpenAI) -> CodingState:
    """Planner agent that generates a plan from the user description and loops
    until the user accepts it.

    If no user_description is provided, prompts the user to enter one.
    If no plan exists, generates one via the LLM and displays it.
    Repeatedly asks for acceptance; if rejected, regenerates with feedback.

    Args:
        state: Current workflow state.
        llm: LangChain LLM instance to use for plan generation.

    Returns:
        Updated state with an accepted plan and task list.
    """
    # --- Ensure user_description exists -----------------------------------
    if not state.get("user_description") or not state["user_description"].strip():
        state["user_description"] = input(
            "Describe the application you want to build: "
        ).strip()
        if not state["user_description"]:
            logger.warning("Empty user description provided; cannot proceed.")
            return state

    # --- Initialize conversation history if needed -------------------------
    if "plan_conversation" not in state or not state["plan_conversation"]:
        state["plan_conversation"] = [
            SystemMessage(content=_load_planner_prompt()),
            HumanMessage(content=f"Plan this application:\n\n{state['user_description']}"),
        ]

    # --- Plan generation loop ----------------------------------------------
    iteration = 0
    while True:
        # Generate or regenerate the plan
        response = llm.invoke(state["plan_conversation"])
        state["plan"] = response.content
        state["plan_conversation"].append(AIMessage(content=response.content))

        # Extract tasks from the plan (simple split on numbered/bulleted lines)
        state["tasks"] = _extract_tasks(state["plan"])
        state["completed_tasks"] = []
        state["prev_step"] = "planner"

        iteration += 1
        print(f"\n{'=' * 60}")
        print(f"  PLAN (iteration {iteration})")
        print(f"{'=' * 60}")
        print(state["plan"])
        print(f"{'=' * 60}\n")

        # Ask for acceptance
        choice = input("Accept this plan? (yes/no/feedback): ").strip().lower()

        if choice in ("yes", "y", ""):
            logger.info("User accepted the plan on iteration %d.", iteration)
            break

        # User rejected or provided feedback — append to conversation and retry
        feedback = choice if choice not in ("no", "n") else "Please revise the plan."
        state["plan_conversation"].append(
            HumanMessage(content=f"Feedback: {feedback}. Please revise.")
        )
        logger.info("User rejected plan; iteration %d — regenerating.", iteration)

    return state


def _extract_tasks(plan: str) -> list[str]:
    """Best-effort extract task lines from a generated plan.

    Looks for lines starting with numbered items (1., 2., …), bullet markers
    (-, *), or checkbox syntax ([ ]).
    """
    tasks: list[str] = []
    for line in plan.splitlines():
        stripped = line.strip()
        if (
            stripped
            and (
                stripped[0].isdigit() and "." in stripped[:4]
                or stripped.startswith(("- ", "* "))
                or stripped.startswith("[ ]")
                or stripped.startswith("[x]")
            )
        ):
            # Clean up leading markers
            import re
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            cleaned = re.sub(r"^[-*]\s*", "", cleaned)
            cleaned = re.sub(r"^\[[ xX]\]\s*", "", cleaned)
            tasks.append(cleaned)
    return tasks if tasks else ["Review and break down the plan into tasks."]
