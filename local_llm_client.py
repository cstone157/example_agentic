"""
Script to call a local LLM running on a Spark DGX.

The local model is assumed to be served via an OpenAI-compatible API
(e.g., vLLM, TGI, Ollama with openai server). Configure the BASE_URL
and MODEL_NAME below to match your deployment.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file (if present)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Configuration ───────────────────────────────────────────────
# Base URL of the local model serving endpoint
# Examples:
#   vLLM:      http://<dgx-host>:8000/v1
#   TGI:       http://<dgx-host>:8080/v1
#   Ollama:    http://localhost:11434/v1
BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")

# Model name as registered on the serving endpoint
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3.6:35b-a3b-bf16")

# API key — Ollama does not require an API key; any string works
API_KEY = os.getenv("LLM_API_KEY", "ollama")

# ── Client setup ────────────────────────────────────────────────
client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


def chat(prompt: str, system_prompt: str | None = None, **kwargs) -> str:
    """Send a chat completion request to the local LLM.

    Parameters
    ----------
    prompt : str
        The user message.
    system_prompt : str, optional
        An optional system/instruction message.
    **kwargs
        Extra parameters forwarded to the OpenAI chat.completions.create call
        (e.g. temperature, max_tokens, top_p).

    Returns
    -------
    str
        The model's response text.
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        **kwargs,
    )
    choice = response.choices[0].message
    # Reasoning models (e.g., Qwen 3.6) may put output in 'reasoning' instead of 'content'
    return choice.reasoning if choice.reasoning else choice.content


def stream_chat(prompt: str, system_prompt: str | None = None, **kwargs):
    """Stream a chat completion from the local LLM.

    Yields chunks of the model's response as they arrive.
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,
        **kwargs,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


# ── Demo / CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Call a local LLM on a Spark DGX")
    parser.add_argument("prompt", help="User prompt to send to the model")
    parser.add_argument("--system", "-s", help="Optional system prompt")
    parser.add_argument("--stream", action="store_true", help="Stream the response")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    if args.stream:
        print("Streaming response:\n" + "-" * 40)
        for chunk in stream_chat(
            args.prompt,
            system_prompt=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ):
            print(chunk, end="", flush=True)
        print("\n" + "-" * 40)
    else:
        response = chat(
            args.prompt,
            system_prompt=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        print(response)
