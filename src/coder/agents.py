import logging
from pathlib import Path

from typing import Literal
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from state import CoderAgentState

logger = logging.getLogger(__name__)

_INITIAL_ = "initial"
_PLANNER_ = "plan"
_TASKER_ = "task"

_llm_ = None
_PLANNER_SYSTEM_PROMPT_ = None



def _init_agents_(llm, planner_prompt=None):
    """
    Initialize the global variables
    Args:
        llm: The llm we should be using
        planner_prompt (str): Optional, the planner prompt if none is specified, it will attempt
                                to pull if from the file system or generate it's own.
    """
    global _llm_, _PLANNER_SYSTEM_PROMPT_
    _llm_ = llm

    if planner_prompt is None:
        planner_path = Path(__file__).resolve().parent.parent / "agents" / "planner" / "agents.md"
        if planner_path.exists():
            with open(planner_path, encoding="utf-8") as _f:
                _PLANNER_SYSTEM_PROMPT_ = _f.read()
        else:
            _PLANNER_SYSTEM_PROMPT_ = (
                "You are an expert software planning agent. Translate the user's program "
                "description into a clear, actionable development plan with file structure, "
                "task list, dependencies, and configuration."
            )
    else:
        _PLANNER_SYSTEM_PROMPT_ = planner_prompt


# ---------------------------------------------------------------------------
# The various different Agents that our application will be using
# ---------------------------------------------------------------------------
def planner_agent(state: CoderAgentState) -> CoderAgentState:
    """
    A agent that will use the user description to generate a plan for 
    building the application.

    Args:
        state (AgentState): The current state containing the user query.
    Returns:
        AgentState: Updated state with the generated plan.
    """    
    # Here you would implement the logic to generate a plan based on the user query.
    # For demonstration purposes, we'll just create a dummy plan.
    logger.info("--- Input Node ---")
    state['user_description'] = input("Describe the application that you want to build: ")

    messages = [
        SystemMessage(content=_PLANNER_SYSTEM_PROMPT_),
        HumanMessage(
            content=(
                f"Describe the application I want built:\n\n{state['user_description']}"
            )
        ),
    ]
    response = _llm_.invoke(messages)
    
    # Update the state with the generated plan
    state['plan'] = response.content
    state['tasks'] = []  # Initialize tasks list
    state['completed_tasks'] = []  # Initialize completed tasks list
    
    logger.info("Generated plan: %s", response.content)
    return state

def task_agent(state: CoderAgentState) -> CoderAgentState:
    """
    A agent that will take the generated plan and break it down into tasks.

    Args:
        state (AgentState): The current state containing the user query and plan.
    Returns:
        AgentState: Updated state with the list of tasks.
    """
    logger.info("--- Task Agent invoked ---")
    if 'plan' not in state or not state['plan']:
        logger.warning("No plan found in state. Cannot generate tasks.")
        return state
    
    # Here you would implement the logic to break down the plan into tasks.
    # For demonstration purposes, we'll just create dummy tasks.
    generated_tasks = [f"Task {i+1} for: {state['plan']}" for i in range(3)]
    
    # Update the state with the generated tasks
    state['tasks'] = generated_tasks
    logger.info("Generated tasks: %s", generated_tasks)
    return state

def initial_agent(state: CoderAgentState) -> Literal["planner_agent", "task_agent"]:
    """
    A initial agent that decides which agent to invoke next based on the user query.

    Args:
        state (AgentState): The current state containing the user query.
    Returns:
        AgentState: Updated state after routing decision.
    """
    logger.info("--- Initial Agent invoked ---")

    if "plan" not in state or state["plan"] is None or state["plan"].strip() == "":
        state['user_description'] = input("Describe the application that you want to build: ")
        state["prev_step"] = _INITIAL_

    logger.info("Current state: %s", state)
    return state


# ---------------------------------------------------------------------------
# The various different routing logic that we will be using
# ---------------------------------------------------------------------------
def router_logic(state: CoderAgentState) -> Literal["planner_agent", "task_agent"]:
    """
    A router agent that decides which agent to invoke next based on the user query.

    Args:
        state (AgentState): The current state containing the user query.
    Returns:
        AgentState: Updated state after routing decision.
    """
    logger.info("--- Router Logic invoked ---")
    logger.info("Current state: %s", state)
    if 'plan' not in state or state['user_description'].strip() == "":
        logger.warning("User query is empty. Routing to planner agent.")
        return "planner_agent"
    
    logger.warning("User query is empty. Routing to task agent.")
    return "task_agent"


def planner_logic(state: CoderAgentState) -> Literal["planner_agent", "task_agent"]