from typing import TypedDict


class CodingState(TypedDict):
    """State for a LangChain coding workflow.

    Tracks the lifecycle from user description through planning, task execution,
    and completion.
    """

    user_description: str
    """Original program description provided by the user."""

    plan: str
    """Generated plan derived from the user description."""

    plan_conversation: list[dict]
    """Conversation history围绕 plan generation (role/content messages)."""

    tasks: list[str]
    """List of tasks to accomplish, derived from the plan."""

    completed_tasks: list[str]
    """List of tasks that have been successfully completed."""

    prev_step: str
    """Name/identifier of the most recently executed step in the workflow."""
