import logging
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

def router_agent(state: CoderAgentState) -> CoderAgentState:
    """
    A router agent that decides which agent to invoke next based on the user query.

    Args:
        state (AgentState): The current state containing the user query.
    Returns:
        AgentState: Updated state after routing decision.
    """
    logger.info("--- Router Agent invoked ---")
    logger.info("Current state: %s", state)
    if 'user_query' not in state or state['user_query'].strip() == "":
        logger.warning("User query is empty. Routing to planner agent.")
        return planner_agent(state)
    
    return state  # No routing needed, return the state unchanged