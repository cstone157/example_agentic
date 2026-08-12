import logging

from typing import Literal
from state import CoderAgentState

logger = logging.getLogger(__name__)

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
    state['user_query'] = input("Input user query: ")
    generated_plan = f"Plan for: {state['user_query']}"
    
    # Update the state with the generated plan
    state['plan'] = generated_plan
    state['tasks'] = []  # Initialize tasks list
    state['completed_tasks'] = []  # Initialize completed tasks list
    
    logger.info("Generated plan: %s", generated_plan)
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
    if 'user_query' not in state or state['user_query'].strip() == "":
        logger.warning("User query is empty. Routing to planner agent.")
        return "planner_agent"
    
    logger.warning("User query is empty. Routing to task agent.")
    return "task_agent"

def router_agent(state: CoderAgentState) -> Literal["planner_agent", "task_agent"]:
    """
    A router agent that decides which agent to invoke next based on the user query.

    Args:
        state (AgentState): The current state containing the user query.
    Returns:
        AgentState: Updated state after routing decision.
    """
    logger.info("--- Router Agent invoked ---")
    logger.info("Current state: %s", state)
    return state