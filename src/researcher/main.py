from collections.abc import Sequence
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import operator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_protocol import Annotated, TypedDict
from langgraph.graph import END, StateGraph


from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.tools import Tool
from langchain import hub


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
TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    research_query: str
    research_results: str
    analysis: str
    final_report: str
    next_agent: str


llm = ChatOpenAI(model=MODEL_NAME, temperature=0.3)

def create_researcher_agent():
    """Agent specialized in finding information"""
    # Define research tools
    def web_search(query: str) -> str:
        """Search the web for information"""
        # Implement with SerpAPI or similar
        from langchain.utilities import SerpAPIWrapper
        search = SerpAPIWrapper()
        return search.run(query)
    
    tools = [
        Tool(
            name="WebSearch",
            func=web_search,
            description="Search the web for current information on any topic"
        )
    ]
    
    prompt = hub.pull("hwchase17/openai-functions-agent")
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)

def researcher_node(state: AgentState) -> AgentState:
    """Research agent that finds information"""
    agent = create_researcher_agent()
    
    result = agent.invoke({
        "input": f"Research the following topic thoroughly: {state['research_query']}"
    })
    
    return {
        "research_results": result["output"],
        "next_agent": "analyst"
    }

def analyst_node(state: AgentState) -> AgentState:
    """Analysis agent that extracts insights"""
    analysis_prompt = f"""
    Analyze the following research results and extract key insights:
    
    Research Results:
    {state['research_results']}
    
    Provide:
    1. Main findings
    2. Important patterns or trends
    3. Potential implications
    """
    
    response = llm.invoke(analysis_prompt)
    
    return {
        "analysis": response.content,
        "next_agent": "writer"
    }

def writer_node(state: AgentState) -> AgentState:
    """Writing agent that creates final report"""
    writing_prompt = f"""
    Create a comprehensive report based on this research and analysis:
    
    Research Results:
    {state['research_results']}
    
    Analysis:
    {state['analysis']}
    
    Write a clear, well-structured report that synthesizes these findings.
    """
    
    response = llm.invoke(writing_prompt)
    
    return {
        "final_report": response.content,
        "next_agent": "END"
    }

def create_research_workflow():
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add agent nodes
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    
    # Define the flow
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)
    
    # Set entry point
    workflow.set_entry_point("researcher")
    
    # Compile into executable graph
    return workflow.compile()

# Use the workflow
app = create_research_workflow()

# Execute the multi-agent system
result = app.invoke({
    "research_query": "What are the latest developments in quantum computing?",
    "messages": [],
    "research_results": "",
    "analysis": "",
    "final_report": "",
    "next_agent": ""
})

print(result["final_report"])