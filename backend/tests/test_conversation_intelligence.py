"""Focused tests for short-term conversational intelligence."""

from app.agent.conversation_state import (
    ConversationState,
    build_conversation_state,
    state_prompt,
)
from app.nlp.intent import Intent


def test_contextual_pronoun_keeps_python_topic():
    first = build_conversation_state(
        "What is Python?",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
    )
    second = build_conversation_state(
        "Is it difficult?",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
        previous=first,
    )
    assert first.current_topic == "Python"
    assert second.current_topic == "Python"
    assert second.unresolved_references == ["it"]
    assert second.predicted_next_action == "CONTINUE_CONTEXT"


def test_machine_learning_followup_keeps_topic():
    first = build_conversation_state(
        "What is machine learning?",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
    )
    second = build_conversation_state(
        "What are its applications?",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
        previous=first,
    )
    assert first.current_topic == "machine learning"
    assert second.current_topic == "machine learning"


def test_topic_switch_to_time_is_not_context_continuation():
    state = build_conversation_state(
        "What time is it?",
        Intent.GET_TIME.value,
        0.96,
        {},
        previous=ConversationState(current_topic="machine learning"),
    )
    assert state.current_intent == Intent.GET_TIME.value
    assert state.predicted_next_action == "ANSWER"


def test_comparison_state_tracks_both_subjects():
    state = build_conversation_state(
        "Compare Python and Java.",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
    )
    assert state.current_topic == "Python and Java"
    assert state.response_strategy == "COMPARISON"


def test_missing_information_is_detected():
    state = build_conversation_state(
        "Set a reminder.",
        Intent.CREATE_REMINDER.value,
        0.94,
        {},
    )
    assert state.missing_information == ["reminder content"]
    assert state.predicted_next_action == "ASK_MISSING_INFORMATION"


def test_state_prompt_is_compact_and_internal():
    state = ConversationState(current_topic="Python", response_strategy="EXPLANATION")
    prompt = state_prompt(state)
    assert "topic: Python" in prompt
    assert "EXPLANATION" in prompt


def test_troubleshooting_request_selects_troubleshooting_strategy():
    state = build_conversation_state(
        "My application crashes with an error.",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
    )
    assert state.response_strategy == "TROUBLESHOOTING"


def test_casual_thanks_selects_casual_strategy():
    state = build_conversation_state(
        "Thanks, Nova.",
        Intent.GENERAL_CONVERSATION.value,
        0.85,
        {},
    )
    assert state.response_strategy == "CASUAL_RESPONSE"


def test_learning_goal_continues_across_turns():
    first = build_conversation_state(
        "I am learning Python.",
        Intent.GENERAL_CONVERSATION.value,
        0.5,
        {},
    )
    second = build_conversation_state(
        "Which projects should I try?",
        Intent.QUESTION_ANSWERING.value,
        0.7,
        {},
        previous=first,
    )
    assert first.user_goal == "learn"
    assert second.user_goal == "learn"


def test_tool_result_is_recorded_for_follow_on_context():
    state = build_conversation_state(
        "Search What is machine learning?",
        Intent.BROWSER_SEARCH.value,
        0.95,
        {"browser_query": "What is machine learning?"},
        tool_name="browser_search",
        tool_result={"success": True},
    )
    assert state.previous_tool == "browser_search"
    assert state.previous_tool_result == {"success": True}
    assert state.task_status == "completed"
    assert state.predicted_next_action == "EXECUTE_TOOL"


def test_low_confidence_state_does_not_invent_a_tool_action():
    state = build_conversation_state(
        "Maybe do something with this.",
        Intent.GENERAL_CONVERSATION.value,
        0.2,
        {},
    )
    assert state.predicted_next_action == "ANSWER"
    assert state.prediction_confidence == 0.2
