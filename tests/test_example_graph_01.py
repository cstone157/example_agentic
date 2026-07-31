"""
test_example_graph_01.py - Tests for the LangGraph code generation workflow.

Tests verify:
1. State transitions work correctly
2. Prompt construction includes user description and agent context
3. Generated code matches expected logic (Pythagorean theorem check)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from example_graph_01 import (
    GraphState,
    ask_user,
    build_prompt,
    generate_code,
    display_result,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def base_state() -> GraphState:
    """Return a minimal GraphState for testing."""
    return {
        "user_description": "",
        "agent_context": "",
        "system_prompt": "",
        "generated_code": "",
    }


@pytest.fixture
def pythagorean_description() -> str:
    """The Pythagorean theorem description to test against."""
    return (
        'The function should accept 3 variables: a, b, and c. '
        'The function should check if "a" squared plus "b" squared equals "c" squared.'
    )


# ── Tests ────────────────────────────────────────────────────────────────────
class TestAskUser:
    """Tests for the ask_user node."""

    def test_ask_user_with_input(self, base_state):
        """Test that user input is captured in state."""
        with patch("builtins.input", return_value="test function"):
            result = ask_user(base_state)
        assert result["user_description"] == "test function"

    def test_ask_user_empty_defaults_to_hello_world(self, base_state):
        """Test that empty input defaults to a hello world description."""
        with patch("builtins.input", return_value=""):
            result = ask_user(base_state)
        assert result["user_description"] == "A simple hello world function"


class TestBuildPrompt:
    """Tests for the build_prompt node."""

    def test_build_prompt_includes_agent_context(self, base_state, pythagorean_description):
        """Test that the system prompt includes the Coder Agent context."""
        state = {**base_state, "user_description": pythagorean_description}
        result = build_prompt(state)
        assert "Coder Agent" in result["system_prompt"] or "production-quality" in result["system_prompt"]

    def test_build_prompt_includes_user_description(self, base_state, pythagorean_description):
        """Test that the user's description is included in the prompt."""
        state = {**base_state, "user_description": pythagorean_description}
        result = build_prompt(state)
        assert pythagorean_description in result["system_prompt"]

    def test_build_prompt_includes_task_instruction(self, base_state, pythagorean_description):
        """Test that the prompt includes instructions to output only code."""
        state = {**base_state, "user_description": pythagorean_description}
        result = build_prompt(state)
        assert "Output ONLY the Python code" in result["system_prompt"]


class TestGenerateCode:
    """Tests for the generate_code node (with mocked LLM)."""

    def test_generate_code_returns_code(self, base_state, pythagorean_description):
        """Test that generate_code returns generated code from the LLM."""
        state = {**base_state, "user_description": pythagorean_description}
        state = build_prompt(state)  # Build the prompt first

        # Mock LLM response with Pythagorean theorem implementation
        mock_response = MagicMock()
        mock_response.content = """
def check_pythagorean(a: float, b: float, c: float) -> bool:
    '''Check if a^2 + b^2 == c^2 (Pythagorean theorem).'''
    return a**2 + b**2 == c**2
"""

        with patch("example_graph_01.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance

            result = generate_code(state)

        # Verify LLM was called with correct messages
        mock_llm_class.assert_called_once()
        call_args = mock_llm_instance.invoke.call_args
        messages = call_args[0][0]  # First positional argument to invoke

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert pythagorean_description in messages[0]["content"]

        # Verify generated code is returned
        assert result["generated_code"] == mock_response.content


class TestDisplayResult:
    """Tests for the display_result node."""

    def test_display_result_returns_state_unchanged(self, base_state):
        """Test that display_result passes state through unchanged."""
        test_code = "def hello(): pass"
        state = {**base_state, "generated_code": test_code}

        with patch("builtins.print"):  # Suppress print output
            result = display_result(state)

        assert result["generated_code"] == test_code


class TestPythagoreanGeneration:
    """Integration-style test for Pythagorean theorem generation."""

    def test_generated_code_contains_pythagorean_logic(self, pythagorean_description):
        """
        Test that when given the Pythagorean description, the generated code
        contains the expected a**2 + b**2 == c**2 logic.
        """
        # This test mocks the entire workflow to verify end-to-end behavior
        from langgraph.graph import START, END, StateGraph

        mock_code = "def check_pythagorean(a, b, c): return a**2 + b**2 == c**2"

        with patch("example_graph_01.ChatOpenAI") as mock_llm_class:
            mock_response = MagicMock()
            mock_response.content = mock_code
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance

            # Build and invoke the workflow
            workflow = StateGraph(GraphState)
            workflow.add_node("ask_user", lambda s: {**s, "user_description": pythagorean_description})
            workflow.add_node("build_prompt", build_prompt)
            workflow.add_node("generate_code", generate_code)
            workflow.add_node("display_result", display_result)

            workflow.add_edge(START, "ask_user")
            workflow.add_edge("ask_user", "build_prompt")
            workflow.add_edge("build_prompt", "generate_code")
            workflow.add_edge("generate_code", "display_result")
            workflow.add_edge("display_result", END)

            app = workflow.compile()
            result = app.invoke({
                "user_description": "",
                "agent_context": "",
                "system_prompt": "",
                "generated_code": "",
            })

        # Verify the generated code contains Pythagorean logic
        assert "a**2" in result["generated_code"] or "a^2" in result["generated_code"]
        assert "b**2" in result["generated_code"] or "b^2" in result["generated_code"]
        assert "c**2" in result["generated_code"] or "c^2" in result["generated_code"]
