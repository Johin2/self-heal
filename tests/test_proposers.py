"""Unit tests for the five LLM proposer adapters.

All tests mock the underlying SDK — no network calls, no API keys needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from self_heal.llm import (
    ClaudeProposer,
    GeminiProposer,
    GroqProposer,
    LiteLLMProposer,
    OpenAIProposer,
)

# ---------------------------------------------------------------------------
# ClaudeProposer
# ---------------------------------------------------------------------------


def _claude_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_claude_proposer_returns_text_from_first_block():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _claude_response("def foo(): return 42")

    with patch("self_heal.llm._claude.Anthropic", return_value=mock_client):
        proposer = ClaudeProposer(model="claude-sonnet-4-6", api_key="test-key")
        result = proposer.propose("sys", "user")

    assert result == "def foo(): return 42"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["system"] == "sys"
    assert call_kwargs["messages"] == [{"role": "user", "content": "user"}]
    assert call_kwargs["max_tokens"] == 2048


def test_claude_proposer_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic-key")
    with patch("self_heal.llm._claude.Anthropic") as MockAnthropic:
        ClaudeProposer()

    MockAnthropic.assert_called_once_with(api_key="env-anthropic-key")


def test_claude_proposer_handles_empty_content():
    mock_client = MagicMock()
    empty_response = MagicMock()
    empty_response.content = []
    mock_client.messages.create.return_value = empty_response

    with patch("self_heal.llm._claude.Anthropic", return_value=mock_client):
        proposer = ClaudeProposer(api_key="x")
        result = proposer.propose("sys", "user")

    assert result == ""


def test_claude_proposer_skips_blocks_without_text():
    mock_client = MagicMock()
    non_text_block = MagicMock(spec=[])  # no .text attribute
    text_block = MagicMock()
    text_block.text = "second block wins"
    response = MagicMock()
    response.content = [non_text_block, text_block]
    mock_client.messages.create.return_value = response

    with patch("self_heal.llm._claude.Anthropic", return_value=mock_client):
        result = ClaudeProposer(api_key="x").propose("sys", "user")

    assert result == "second block wins"


def test_claude_proposer_respects_custom_max_tokens():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _claude_response("code")

    with patch("self_heal.llm._claude.Anthropic", return_value=mock_client):
        ClaudeProposer(api_key="x", max_tokens=512).propose("s", "u")

    assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 512


# ---------------------------------------------------------------------------
# OpenAIProposer
# ---------------------------------------------------------------------------


def _openai_response(content: str | None) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def test_openai_proposer_returns_message_content():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _openai_response(
        "def foo(): return 42"
    )

    with patch("self_heal.llm._openai.OpenAI", return_value=mock_client):
        proposer = OpenAIProposer(model="gpt-5", api_key="test")
        result = proposer.propose("sys", "user")

    assert result == "def foo(): return 42"
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-5"
    assert kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    assert "max_completion_tokens" not in kwargs


def test_openai_proposer_passes_base_url_for_compatible_endpoints():
    with patch("self_heal.llm._openai.OpenAI") as MockOpenAI:
        OpenAIProposer(
            model="llama3.3",
            api_key="ollama",
            base_url="http://localhost:11434/v1",
        )

    MockOpenAI.assert_called_once_with(
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    )


def test_openai_proposer_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    with patch("self_heal.llm._openai.OpenAI") as MockOpenAI:
        OpenAIProposer()

    MockOpenAI.assert_called_once_with(api_key="env-openai-key", base_url=None)


def test_openai_proposer_passes_max_completion_tokens_when_set():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _openai_response("x")

    with patch("self_heal.llm._openai.OpenAI", return_value=mock_client):
        OpenAIProposer(api_key="x", max_tokens=1024).propose("s", "u")

    assert (
        mock_client.chat.completions.create.call_args.kwargs["max_completion_tokens"]
        == 1024
    )


def test_openai_proposer_handles_none_content():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _openai_response(None)

    with patch("self_heal.llm._openai.OpenAI", return_value=mock_client):
        result = OpenAIProposer(api_key="x").propose("s", "u")

    assert result == ""


def test_groq_proposer_sets_default_base_url_and_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-groq-key")
    with patch("self_heal.llm._openai.OpenAI") as MockOpenAI:
        proposer = GroqProposer()

    MockOpenAI.assert_called_once_with(
        api_key="env-groq-key",
        base_url="https://api.groq.com/openai/v1",
    )
    assert proposer.model == "llama-3.3-70b-versatile"


def test_groq_proposer_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch("self_heal.llm._openai.OpenAI") as MockOpenAI:
        GroqProposer(api_key="explicit")

    MockOpenAI.assert_called_once_with(
        api_key="explicit",
        base_url="https://api.groq.com/openai/v1",
    )


# ---------------------------------------------------------------------------
# GeminiProposer
# ---------------------------------------------------------------------------


def test_gemini_proposer_returns_text():
    mock_response = MagicMock()
    mock_response.text = "def foo(): return 42"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("self_heal.llm._gemini.genai.Client", return_value=mock_client):
        result = GeminiProposer(model="gemini-2.5-pro", api_key="test").propose(
            "sys", "user"
        )

    assert result == "def foo(): return 42"
    call = mock_client.models.generate_content.call_args
    assert call.kwargs["model"] == "gemini-2.5-pro"
    assert call.kwargs["contents"] == "user"
    assert call.kwargs["config"].system_instruction == "sys"


def test_gemini_proposer_prefers_gemini_api_key_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

    with patch("self_heal.llm._gemini.genai.Client") as MockClient:
        GeminiProposer()

    MockClient.assert_called_once_with(api_key="gemini-key")


def test_gemini_proposer_falls_back_to_google_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

    with patch("self_heal.llm._gemini.genai.Client") as MockClient:
        GeminiProposer()

    MockClient.assert_called_once_with(api_key="google-key")


def test_gemini_proposer_handles_none_text():
    mock_response = MagicMock()
    mock_response.text = None
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("self_heal.llm._gemini.genai.Client", return_value=mock_client):
        result = GeminiProposer(api_key="x").propose("s", "u")

    assert result == ""


# ---------------------------------------------------------------------------
# LiteLLMProposer
# ---------------------------------------------------------------------------


def _litellm_response(content: str | None) -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    response.choices = [choice]
    return response


def test_litellm_proposer_returns_message_content():
    with patch(
        "self_heal.llm._litellm.completion",
        return_value=_litellm_response("def foo(): return 42"),
    ) as mock_completion:
        result = LiteLLMProposer(model="groq/llama-3.3-70b-versatile").propose(
            "sys", "user"
        )

    assert result == "def foo(): return 42"
    kwargs = mock_completion.call_args.kwargs
    assert kwargs["model"] == "groq/llama-3.3-70b-versatile"
    assert kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    assert "max_tokens" not in kwargs


def test_litellm_proposer_forwards_max_tokens():
    with patch(
        "self_heal.llm._litellm.completion",
        return_value=_litellm_response("code"),
    ) as mock_completion:
        LiteLLMProposer(model="gpt-5", max_tokens=1024).propose("s", "u")

    assert mock_completion.call_args.kwargs["max_tokens"] == 1024


def test_litellm_proposer_forwards_extra_kwargs():
    with patch(
        "self_heal.llm._litellm.completion",
        return_value=_litellm_response("code"),
    ) as mock_completion:
        LiteLLMProposer(
            model="anthropic/claude-sonnet-4-6",
            temperature=0.2,
            api_base="https://custom.example/v1",
        ).propose("s", "u")

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["api_base"] == "https://custom.example/v1"


def test_litellm_proposer_handles_none_content():
    with patch(
        "self_heal.llm._litellm.completion",
        return_value=_litellm_response(None),
    ):
        result = LiteLLMProposer(model="gpt-5").propose("s", "u")

    assert result == ""


# ---------------------------------------------------------------------------
# RepairLoop integration: default proposer is lazily created
# ---------------------------------------------------------------------------


def test_repair_loop_does_not_instantiate_default_at_construction():
    from self_heal import RepairLoop

    with patch("self_heal.llm._claude.Anthropic") as MockAnthropic:
        loop = RepairLoop()  # no proposer passed
        MockAnthropic.assert_not_called()
        assert loop._proposer is None


def test_repair_loop_lazily_creates_claude_proposer_on_access():
    from self_heal import RepairLoop

    with patch("self_heal.llm._claude.Anthropic") as MockAnthropic:
        loop = RepairLoop(model="claude-sonnet-4-6")
        _ = loop.proposer
        MockAnthropic.assert_called_once()


def test_repair_loop_uses_passed_proposer_directly():
    from self_heal import RepairLoop

    class Dummy:
        def propose(self, system: str, user: str) -> str:
            return "def f(): pass"

    dummy = Dummy()
    with patch("self_heal.llm._claude.Anthropic") as MockAnthropic:
        loop = RepairLoop(proposer=dummy)
        assert loop.proposer is dummy
        MockAnthropic.assert_not_called()


def test_repair_loop_rejects_invalid_max_attempts():
    from self_heal import RepairLoop

    with pytest.raises(ValueError):
        RepairLoop(max_attempts=0)
