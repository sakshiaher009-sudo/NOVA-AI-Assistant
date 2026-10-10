"""NOVA — Backend Tests: NLP Pipeline."""

import pytest
from app.nlp.preprocessing import normalize_text, expand_contractions, clean_for_intent
from app.nlp.language_detection import detect_language
from app.nlp.intent import classify_intent, Intent
from app.nlp.entities import extract_entities, resolve_time
from app.nlp.classifier import analyze
from app.agent.orchestrator import _resolve_clarification_reply, _website_followup_state
from app.tools.base import ToolResult


class TestPreprocessing:
    def test_normalize_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_normalize_empty(self):
        assert normalize_text("") == ""

    def test_expand_contractions(self):
        assert "do not" in expand_contractions("don't do that")
        assert "i am" in expand_contractions("I'm here")

    def test_clean_for_intent(self):
        result = clean_for_intent("What's the TIME?")
        assert "time" in result
        assert result.islower() or "?" in result


class TestLanguageDetection:
    def test_english(self):
        assert detect_language("What is machine learning?") == "en"

    def test_english_short(self):
        assert detect_language("Hello there") == "en"

    def test_empty(self):
        assert detect_language("") == "unknown"


class TestIntentClassification:
    def test_calculate(self):
        intent, conf = classify_intent("what is 5 + 3")
        assert intent == Intent.CALCULATE

    def test_calculate_expression(self):
        intent, conf = classify_intent("987 * 43")
        assert intent == Intent.CALCULATE

    def test_get_time(self):
        intent, conf = classify_intent("what time is it")
        assert intent == Intent.GET_TIME

    def test_create_note(self):
        intent, conf = classify_intent("remember that I need to study tonight")
        assert intent == Intent.CREATE_NOTE

    def test_list_notes(self):
        intent, conf = classify_intent("show my notes")
        assert intent == Intent.LIST_NOTES

    def test_create_reminder(self):
        intent, conf = classify_intent("remind me to practice Python tomorrow")
        assert intent == Intent.CREATE_REMINDER

    def test_document_search(self):
        intent, conf = classify_intent("find support vector machines in my PDF")
        assert intent == Intent.DOCUMENT_SEARCH

    def test_greeting(self):
        intent, conf = classify_intent("hello")
        assert intent == Intent.GENERAL_CONVERSATION

    def test_system_status(self):
        intent, conf = classify_intent("system status")
        assert intent == Intent.SYSTEM_STATUS

    def test_question(self):
        intent, conf = classify_intent("what is overfitting in machine learning")
        assert intent == Intent.QUESTION_ANSWERING

    @pytest.mark.parametrize(
        "message",
        [
            "What is machine learning?",
            "Explain neural networks.",
            "What is the difference between AI and ML?",
        ],
    )
    def test_general_questions_are_not_actionable_tools(self, message):
        intent, _ = classify_intent(message)
        assert intent == Intent.QUESTION_ANSWERING
        assert intent not in {Intent.GET_TIME, Intent.CALCULATE}

    def test_memory_search(self):
        intent, conf = classify_intent("do you remember what I said about databases")
        assert intent == Intent.SEARCH_MEMORY

    def test_delete_note(self):
        intent, conf = classify_intent("delete the note about databases")
        assert intent == Intent.DELETE_NOTE

    def test_document_summary(self):
        intent, conf = classify_intent("summarize this document")
        assert intent == Intent.DOCUMENT_SUMMARY

    def test_open_application(self):
        intent, conf = classify_intent("open the application Safari")
        assert intent == Intent.OPEN_APPLICATION

    def test_file_search(self):
        intent, conf = classify_intent("find my notes files")
        assert intent == Intent.FILE_SEARCH

    def test_browser_search_general_question(self):
        intent, conf = classify_intent("search What is Machine Learning?")
        assert intent not in {Intent.DOCUMENT_SEARCH, Intent.FILE_SEARCH}

    def test_read_file(self):
        intent, conf = classify_intent("read this text file")
        assert intent == Intent.READ_FILE

    def test_execute_terminal(self):
        intent, conf = classify_intent("check python version in terminal")
        assert intent == Intent.EXECUTE_TERMINAL

    def test_unknown_empty(self):
        intent, conf = classify_intent("")
        assert intent == Intent.UNKNOWN


class TestEntityExtraction:
    def test_numbers(self):
        result = extract_entities("calculate 42 plus 58")
        assert "numbers" in result
        assert 42 in result["numbers"]

    def test_math_expression(self):
        result = extract_entities("what is 987 * 43")
        assert "math_expression" in result
        assert "987 * 43" in result["math_expression"]

    def test_time(self):
        result = extract_entities("remind me at 7:30 PM")
        assert "time" in result

    def test_date(self):
        result = extract_entities("schedule for tomorrow")
        assert "date" in result
        assert result["date"] == "tomorrow"

    def test_task(self):
        result = extract_entities("remember to study machine learning")
        assert "task" in result
        assert "study machine learning" in result["task"]

    def test_resolve_time_pm(self):
        assert resolve_time("7 PM") == "19:00"

    def test_resolve_time_noon(self):
        assert resolve_time("noon") == "12:00"

    def test_resolve_time_24h(self):
        assert resolve_time("14:30") == "14:30"


@pytest.mark.asyncio
class TestOpenRouting:
    async def test_google_routes_to_website(self):
        result = await analyze("open Google", use_llm_fallback=False)
        assert result.intent == Intent.OPEN_WEBSITE.value

    async def test_terminal_routes_to_application(self):
        result = await analyze("open Terminal", use_llm_fallback=False)
        assert result.intent == Intent.OPEN_APPLICATION.value

    async def test_safari_routes_to_application(self):
        result = await analyze("open Safari", use_llm_fallback=False)
        assert result.intent == Intent.OPEN_APPLICATION.value

    async def test_spotify_requires_clarification(self):
        result = await analyze("open Spotify", use_llm_fallback=False)
        assert result.intent == Intent.OPEN_AMBIGUOUS.value

    async def test_website_followup_resolves_original_name(self):
        result = _resolve_clarification_reply(
            "its website",
            {"original_name": "Chat GPT", "awaiting": "app_or_website"},
        )
        assert result.intent == Intent.OPEN_WEBSITE.value
        assert result.entities == {"app_name": "Chat GPT"}


@pytest.mark.asyncio
class TestSearchRouting:
    async def test_general_search_routes_to_browser(self):
        result = await analyze("search What is Machine Learning?", use_llm_fallback=False)
        assert result.intent == "BROWSER_SEARCH"

    async def test_document_search_regression(self):
        result = await analyze(
            "search my documents for the Q3 report", use_llm_fallback=False
        )
        assert result.intent == Intent.DOCUMENT_SEARCH.value

    async def test_file_search_regression(self):
        result = await analyze(
            "find my package.json file", use_llm_fallback=False
        )
        assert result.intent == Intent.FILE_SEARCH.value

    async def test_ambiguous_search_requires_clarification(self):
        result = await analyze("search invoice", use_llm_fallback=False)
        assert result.intent == "SEARCH_AMBIGUOUS"


class TestWebsiteFollowups:
    def test_google_success_creates_search_pending_state(self):
        pending = _website_followup_state(
            ToolResult(success=True, result={"site_name": "Google", "url": "https://www.google.com"})
        )
        assert pending == {
            "awaiting": "search_query_for_google",
            "original_name": "Google",
        }

    def test_google_followup_becomes_browser_search(self):
        result = _resolve_clarification_reply(
            "Search What is Machine Learning?",
            {"awaiting": "search_query_for_google", "original_name": "Google"},
        )
        assert result.intent == "BROWSER_SEARCH"
        assert result.entities == {"browser_query": "What is Machine Learning?"}

    def test_google_topic_change_bypasses_pending_state(self):
        result = _resolve_clarification_reply(
            "Actually open YouTube",
            {"awaiting": "search_query_for_google", "original_name": "Google"},
        )
        assert result is None

    def test_multiple_sequential_searches_remain_direct_searches(self):
        pending = {"awaiting": "search_query_for_google", "original_name": "Google"}
        first = _resolve_clarification_reply("Search cats", pending)
        second = _resolve_clarification_reply("Search dogs", pending)
        assert first.entities["browser_query"] == "cats"
        assert second.entities["browser_query"] == "dogs"

    def test_gmail_followup_is_acknowledgement_only(self):
        result = _resolve_clarification_reply(
            "find the email from Alex",
            {"awaiting": "gmail_followup", "original_name": "Gmail"},
        )
        assert result.intent == "FOLLOWUP_ACKNOWLEDGEMENT"

    def test_unrelated_time_message_bypasses_google_pending_state(self):
        result = _resolve_clarification_reply(
            "what time is it",
            {"awaiting": "search_query_for_google", "original_name": "Google"},
        )
        assert result is None
