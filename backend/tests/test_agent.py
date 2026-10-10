"""NOVA — Backend Tests: Agent."""

import pytest
from app.agent.context import build_context
from app.agent.router import allows_llm_tool_calls
from app.agent.conversation_state import ConversationState
from app.nlp.intent import Intent
from app.schemas.chat import NLPResult
from app.agent.prompts import get_system_prompt
from app.agent.response import format_tool_response, format_error_response
from app.tools.base import ToolResult


class TestContext:
    def test_empty_history(self):
        msgs = build_context([])
        assert len(msgs) >= 1  # At least system prompt
        assert msgs[0].role == "system"

    def test_sliding_window(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(30)]
        msgs = build_context(history, max_messages=5)
        # System prompt + summary prompt + 5 recent messages
        assert len(msgs) == 7
        assert "Earlier conversation context summary" in msgs[1].content
        assert msgs[-1].content == "msg 29"

    def test_preserves_roles(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        msgs = build_context(history)
        roles = [m.role for m in msgs]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" in roles

    def test_conversational_question_does_not_offer_tools_to_llm(self):
        result = NLPResult(
            intent=Intent.QUESTION_ANSWERING.value,
            confidence=0.70,
            entities={},
            language="en",
        )
        assert allows_llm_tool_calls(result) is False

    def test_general_conversation_does_not_offer_tools_to_llm(self):
        result = NLPResult(
            intent=Intent.GENERAL_CONVERSATION.value,
            confidence=0.40,
            entities={},
            language="en",
        )
        assert allows_llm_tool_calls(result) is False

    def test_explicit_time_and_calculation_can_use_tools(self):
        for intent in (Intent.GET_TIME, Intent.CALCULATE):
            result = NLPResult(
                intent=intent.value,
                confidence=0.95,
                entities={},
                language="en",
            )
            assert allows_llm_tool_calls(result) is True

    def test_conversation_prompt_omits_tool_catalog(self):
        prompt = get_system_prompt(include_tools=False)
        assert "Conversation Mode" in prompt
        assert "Available Tools" not in prompt
        assert "internal reasoning" in prompt

    def test_context_includes_relevant_state_and_memory(self):
        msgs = build_context(
            [{"role": "user", "content": "What is Python?"}],
            conversation_state=ConversationState(
                current_topic="Python",
                unresolved_references=["it"],
            ),
            current_message="Is it good for beginners?",
            relevant_memory=[{"content": "The user is learning Python."}],
            include_tools=False,
        )
        text = "\n".join(msg.content for msg in msgs)
        assert "resolved reference topic: Python" in text
        assert "The user is learning Python." in text
        assert "Available Tools" not in text

    def test_context_bounds_old_unrelated_history(self):
        history = [
            {"role": "user", "content": "Unrelated topic number one"},
            {"role": "assistant", "content": "Unrelated answer"},
        ] + [
            {"role": "user", "content": f"Python detail {i}"}
            for i in range(12)
        ]
        msgs = build_context(
            history,
            max_messages=6,
            current_message="Tell me more about Python",
            conversation_state=ConversationState(current_topic="Python"),
            include_tools=False,
        )
        contents = [msg.content for msg in msgs]
        assert "Python detail 11" in contents[-1]
        assert "Unrelated topic number one" not in "\n".join(contents)


class TestResponse:
    def test_format_tool_success(self):
        result = ToolResult(success=True, display_text="2 + 2 = 4")
        text = format_tool_response("calculator", result)
        assert "4" in text

    def test_format_tool_error(self):
        result = ToolResult(success=False, error="Division by zero")
        text = format_tool_response("calculator", result)
        assert "error" in text.lower()

    def test_error_messages(self):
        msg = format_error_response("ollama_unavailable")
        assert "ollama" in msg.lower() or "language model" in msg.lower()

        msg = format_error_response("stt_unavailable")
        assert "speech" in msg.lower()
