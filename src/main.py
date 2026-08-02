"""LangGraph chat agent powered by a local LLM on a Spark DGX.

The local model is served via an OpenAI-compatible API (e.g., Ollama).
Configure the environment variables or edit the defaults below to match
your deployment.
"""

import argparse
import os
from pathlib import Path
from typing import Annotated, TypedDict

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
# LangGraph state definition
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """The state carried through the graph.

    Attributes:
        messages: The conversation history as a list of LangChain message objects.
        temperature: Sampling temperature for the LLM.
        max_tokens: Maximum tokens in the response.
    """

    messages: Annotated[list, "messages"]
    temperature: float
    max_tokens: int


# ---------------------------------------------------------------------------
# LLM node
# ---------------------------------------------------------------------------


def chat_node(state: AgentState) -> AgentState:
    """Call the local LLM and return the assistant response.

    Args:
        state: Current graph state containing the message history,
            temperature, and max_tokens.

    Returns:
        Updated state with the assistant's reply appended to messages.
    """
    messages = state["messages"]
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=state.get("temperature", 0.7),
        max_tokens=state.get("max_tokens", 1024),
    )
    response = llm.invoke(messages)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)
workflow.add_node("chat", chat_node)
workflow.set_entry_point("chat")
workflow.add_edge("chat", END)
graph = workflow.compile()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_chat(
    prompt: str,
    system_prompt: str | None = None,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> None:
    """Run a single-turn chat interaction through the LangGraph agent.

    Args:
        prompt: The user message to send.
        system_prompt: Optional system/instruction message prepended to history.
        stream: If True, attempt streaming (not all models/backends support it).
        temperature: Sampling temperature for the LLM.
        max_tokens: Maximum tokens in the response.
    """
    messages: list = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    initial_state: AgentState = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if stream:
        print("Streaming response:\n" + "-" * 40)
        for chunk in graph.stream(initial_state, stream_mode="updates"):
            for _node, data in chunk.items():
                msg = data.get("messages", [])[-1]
                if hasattr(msg, "content") and msg.content:
                    print(msg.content, end="", flush=True)
        print("\n" + "-" * 40)
    else:
        result = graph.invoke(initial_state)
        assistant_msg = result["messages"][-1]
        print(assistant_msg.content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph chat agent for a local LLM")
    parser.add_argument("prompt", help="User prompt to send to the model")
    parser.add_argument("--system", "-s", help="Optional system prompt")
    parser.add_argument("--stream", action="store_true", help="Stream the response")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=1024, help="Maximum tokens in response")
    args = parser.parse_args()

    run_chat(prompt=args.prompt, system_prompt=args.system, stream=args.stream)
