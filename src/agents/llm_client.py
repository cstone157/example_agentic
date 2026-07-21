"""LLM Client Abstraction Layer.

Provides a unified interface for calling LLMs across multiple providers
(OpenAI, Anthropic, etc.) while maintaining consistent prompts and responses
for the multi-agent workflow.

Designed to support swapping providers without changing agent code.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ── Provider Registry ────────────────────────────────────────────────

_PROVIDER_MAP: dict[str, type["BaseLLMClient"]] = {}


def register_provider(name: str):
    """Decorator to register an LLM provider class."""
    def decorator(cls: type["BaseLLMClient"]) -> type["BaseLLMClient"]:
        _PROVIDER_MAP[name] = cls
        return cls
    return decorator


# ── Base Client Interface ────────────────────────────────────────────

class BaseLLMClient:
    """Abstract base class for LLM clients.

    Subclasses implement provider-specific logic while exposing a
    consistent interface to the workflow nodes.
    """

    provider_name: str = "base"

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.0, **kwargs: Any) -> None:
        self.model = model
        self.temperature = temperature
        self.extra_kwargs = kwargs

    def invoke(
        self,
        system_prompt: str,
        user_input: str,
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke the LLM and return structured output.

        Args:
            system_prompt: System message defining agent role and instructions.
            user_input: User/application input to process.
            response_format: Optional Pydantic model or dict schema for structured output.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Parsed response (string, dict, or Pydantic model instance).
        """
        raise NotImplementedError("Subclasses must implement invoke()")

    def invoke_messages(
        self,
        messages: list[Any],
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke the LLM with a list of pre-built messages.

        Args:
            messages: List of langchain message objects.
            response_format: Optional structured output format.
            **kwargs: Additional parameters.

        Returns:
            Parsed response.
        """
        raise NotImplementedError("Subclasses must implement invoke_messages()")


# ── OpenAI Client ────────────────────────────────────────────────────

@register_provider("openai")
class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client using langchain-openai.

    Supports all OpenAI chat models (gpt-4o, gpt-4-turbo, etc.) as well as
    any OpenAI-compatible API endpoint for local models (Ollama, LM Studio,
    vLLM, text-generation-inference, etc.).

    Configuration via environment variables:
        OPENAI_API_KEY     — Required API key (or "local" for no auth)
        OPENAI_MODEL       — Model name (default: gpt-4o)
        OPENAI_TEMP        — Temperature (default: 0.0)
        OPENAI_BASE_URL    — Custom API endpoint URL (for local models)

    For local models, set OPENAI_BASE_URL to your endpoint and use a dummy key:
        export OPENAI_BASE_URL=http://localhost:11434/v1
        export OPENAI_API_KEY=local
        export OPENAI_MODEL=llama3.2
    """

    provider_name = "openai"

    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None, **kwargs: Any) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = temperature if temperature is not None else float(os.getenv("OPENAI_TEMP", "0.0"))
        self.api_key = os.getenv("OPENAI_API_KEY", "local")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.extra_kwargs = kwargs

        logger.info(
            "Initializing OpenAIClient(model=%s, temp=%.1f, base_url=%s)",
            self.model, self.temperature, self.base_url,
        )
        self._llm: Optional[ChatOpenAI] = None

    @property
    def llm(self) -> ChatOpenAI:
        """Lazy-initialize the underlying ChatOpenAI instance."""
        if self._llm is None:
            init_kwargs: dict[str, Any] = {
                "model": self.model,
                "temperature": self.temperature,
                "api_key": self.api_key,
            }
            if self.base_url:
                init_kwargs["base_url"] = self.base_url
            init_kwargs.update(self.extra_kwargs)
            self._llm = ChatOpenAI(**init_kwargs)
        return self._llm

    def invoke(
        self,
        system_prompt: str,
        user_input: str,
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke OpenAI with system + user messages."""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ])

        chain = prompt | self._configure_output(response_format)
        result = chain.invoke({})
        return self._parse_result(result, response_format)

    def invoke_messages(
        self,
        messages: list[Any],
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke OpenAI with pre-built message list."""
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | self._configure_output(response_format)
        result = chain.invoke({})
        return self._parse_result(result, response_format)

    def _configure_output(self, response_format: Optional[type]) -> Any:
        """Configure structured output if a format is specified."""
        llm = self.llm
        if response_format is not None:
            # Use Pydantic model for structured output
            if hasattr(response_format, "model_json_schema"):
                llm = llm.with_structured_output(response_format)
            else:
                # Fallback: use dict schema
                llm = llm.with_structured_output(response_format)
        return llm

    def _parse_result(self, result: Any, response_format: Optional[type]) -> Any:
        """Parse LLM result into the expected format."""
        if response_format is not None and hasattr(response_format, "model_validate"):
            return response_format.model_validate(result)
        if hasattr(result, "content"):
            content = result.content
            # Try parsing JSON if the response looks like JSON
            if content.strip().startswith("{") or content.strip().startswith("["):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
            return content
        return result


# ── Anthropic Client (Stub — extend as needed) ───────────────────────

@register_provider("anthropic")
class AnthropicClient(BaseLLMClient):
    """Anthropic Claude LLM client.

    Configuration via environment variables:
        ANTHROPIC_API_KEY  — Required API key
        ANTHROPIC_MODEL    — Model name (default: claude-sonnet-4-20250514)
    """

    provider_name = "anthropic"

    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None, **kwargs: Any) -> None:
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        self.temperature = temperature if temperature is not None else 0.0
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.extra_kwargs = kwargs

    def invoke(
        self,
        system_prompt: str,
        user_input: str,
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke Anthropic Claude."""
        from langchain_anthropic import ChatAnthropic

        init_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.api_key:
            init_kwargs["api_key"] = self.api_key
        init_kwargs.update(self.extra_kwargs)

        llm = ChatAnthropic(**init_kwargs)
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ])

        if response_format is not None:
            llm = llm.with_structured_output(response_format)

        chain = prompt | llm
        result = chain.invoke({})

        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = content[0].text if hasattr(content[0], "text") else str(content[0])

        if content.strip().startswith("{") or content.strip().startswith("["):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return content

    def invoke_messages(
        self,
        messages: list[Any],
        response_format: Optional[type] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke Anthropic with pre-built message list."""
        from langchain_anthropic import ChatAnthropic

        init_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.api_key:
            init_kwargs["api_key"] = self.api_key
        init_kwargs.update(self.extra_kwargs)

        llm = ChatAnthropic(**init_kwargs)
        prompt = ChatPromptTemplate.from_messages(messages)

        if response_format is not None:
            llm = llm.with_structured_output(response_format)

        chain = prompt | llm
        result = chain.invoke({})

        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = content[0].text if hasattr(content[0], "text") else str(content[0])

        if content.strip().startswith("{") or content.strip().startswith("["):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return content


# ── Client Factory ───────────────────────────────────────────────────

def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs: Any,
) -> BaseLLMClient:
    """Factory function to create an LLM client.

    Args:
        provider: Provider name ('openai', 'anthropic', etc.).
                  Defaults to OPENAI_PROVIDER env var or 'openai'.
        model: Model name (provider-specific).
        temperature: Sampling temperature (0.0–1.0).
        **kwargs: Additional parameters passed to the client.

    Returns:
        Configured LLM client instance.

    Raises:
        ValueError: If the provider is not registered.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "openai")

    if provider not in _PROVIDER_MAP:
        available = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available providers: {available}"
        )

    client_cls = _PROVIDER_MAP[provider]
    logger.info("Creating LLM client: provider=%s, model=%s", provider, model)
    return client_cls(model=model, temperature=temperature, **kwargs)


# ── Convenience Function for Agents ──────────────────────────────────

def call_llm_agent(
    agent_config_path: str,
    input_data: str,
    client: Optional[BaseLLMClient] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """High-level function to call an LLM agent with its config file.

    Reads the AGENTS.md config file to extract system prompt, then
    invokes the LLM client with the provided input.

    Args:
        agent_config_path: Path to the AGENTS.md file for the agent.
        input_data: Input string to send to the agent.
        client: Optional pre-configured LLM client.
        provider: Provider name (used if client is not provided).
        **kwargs: Additional parameters passed to the client.

    Returns:
        Parsed response as a dictionary.
    """
    # Read agent config
    with open(agent_config_path, "r", encoding="utf-8") as f:
        config_content = f.read()

    # Extract system prompt from config (everything after "## Role" and before next section)
    system_prompt = _extract_system_prompt(config_content)

    # Get or create client
    if client is None:
        client = get_llm_client(provider=provider, **kwargs)

    # Invoke the agent
    response = client.invoke(
        system_prompt=system_prompt,
        user_input=input_data,
        **kwargs,
    )

    # Parse response
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"response": response}
    return {"response": str(response)}


def _extract_system_prompt(config_content: str) -> str:
    """Extract the system prompt from an AGENTS.md config file.

    Extracts content from '## Role' section through to the next major section.
    Falls back to the full content if no clear sections are found.
    """
    lines = config_content.split("\n")
    role_start = None
    role_end = len(lines)

    for i, line in enumerate(lines):
        if line.startswith("## Role"):
            role_start = i + 1
        elif role_start is not None and line.startswith("## "):
            role_end = i
            break

    if role_start is not None:
        prompt_lines = lines[role_start:role_end]
        return "\n".join(line.strip() for line in prompt_lines if line.strip())

    # Fallback: return first non-empty line after title
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("#"):
            return "\n".join(lines[i:])
    return config_content
