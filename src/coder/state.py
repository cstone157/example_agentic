from typing import TypedDict                              # Used to define structured state

# ---------------------------------------------------------------------------
# Create a TypedDict to define the structure of the agent's state, it will
# include the users original program description, generated plan, a list of 
# tasks to be completed, and a list of completed tasks.
# ---------------------------------------------------------------------------
class CoderAgentState(TypedDict):
    prev_step: str
    user_description: str
    plan: str
    plan_conversation: list
    tasks: list[str]
    completed_tasks: list[str]