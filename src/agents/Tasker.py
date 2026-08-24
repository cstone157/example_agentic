import logging
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state.CodingState import CodingState

logger = logging.getLogger(__name__)

_TASKER_SYSTEM_PROMPT_ = (
    "You are an expert software task decomposition agent. Your job is to take a "
    "development plan and break it down into a detailed, ordered list of executable "
    "tasks with unique identifiers."
)
_llm_ = None

def _init_tasker_(llm) -> str:
    """Load tasker prompt from agents.md if available."""
    global _llm_, _TASKER_SYSTEM_PROMPT_
    _llm_ = llm

    tasker_path = Path(__file__).resolve().parent.parent / "agents" / "tasker" / "agents.md"
    if tasker_path.exists():
        with open(tasker_path, encoding="utf-8") as f:
            _TASKER_SYSTEM_PROMPT_ = f.read()


def tasker_agent(state: CodingState) -> CodingState:
    """Tasker agent that takes an accepted plan from state and generates a list of tasks.

    If no plan exists in state, logs a warning and returns unchanged state.
    Uses the tasker prompt (from agents/tasker/agents.md or fallback) to guide
    the LLM in decomposing the plan into granular, dependency-ordered tasks with
    unique identifiers (e.g., T-AUTH-01, T-DB-02).

    Args:
        state: Current workflow state containing an accepted plan.

    Returns:
        Updated state with tasks populated and prev_step set to "tasker".
    """
    # --- Ensure a plan exists ------------------------------------------------
    if not state.get("plan") or not state["plan"].strip():
        logger.warning("No plan found in state; cannot generate tasks.")
        return state

    # --- Build conversation --------------------------------------------------
    tasker_conversation: list = [
        SystemMessage(content=_TASKER_SYSTEM_PROMPT_),
        HumanMessage(
            content=(
                f"Decompose the following plan into a detailed task list:\n\n"
                f"{state['plan']}"
            )
        ),
    ]

    response = _llm_.invoke(tasker_conversation)
    task_text = response.content

    # Append to conversation history for potential follow-up
    tasker_conversation.append(AIMessage(content=task_text))

    # --- Extract tasks from the LLM output -----------------------------------
    state["tasks"] = _extract_tasks(task_text)
    state["completed_tasks"] = []
    state["prev_step"] = "tasker"

    logger.info("Generated %d tasks from plan.", len(state["tasks"]))
    print(f"\nGenerated {len(state['tasks'])} tasks:\n")
    for task in state["tasks"]:
        print(f"  - {task}")
    print()

    return state


def _extract_tasks(task_text: str) -> list[str]:
    """Extract individual task lines from the LLM-generated task list.

    Looks for lines starting with:
    - Numbered items (1., 2., …)
    - Bullet markers (-, *)
    - Task IDs matching T-[A-Z]+-NN pattern (e.g., T-AUTH-01)
    - Markdown headers like ### T-ID: Title

    Returns a list of cleaned task descriptions.
    """
    tasks: list[str] = []
    for line in task_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Match ### T-[ID]: Title pattern
        if stripped.startswith("### T-"):
            import re
            match = re.search(r"T-[A-Z]+-\d+:\s*(.+)", stripped)
            if match:
                tasks.append(match.group(1).strip())
            continue

        # Match bullet/numbered lines
        if (
            stripped[0].isdigit() and "." in stripped[:4]
            or stripped.startswith(("- ", "* "))
            or stripped.startswith("[ ]")
            or stripped.startswith("[x]")
        ):
            import re
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            cleaned = re.sub(r"^[-*]\s*", "", cleaned)
            cleaned = re.sub(r"^\[[ xX]\]\s*", "", cleaned)
            # Skip lines that are acceptance criteria or metadata
            if not cleaned.startswith(("File:", "Dependencies:", "Module:", "Acceptance")):
                tasks.append(cleaned.strip())

    return tasks if tasks else ["Review and break down the plan into tasks."]
