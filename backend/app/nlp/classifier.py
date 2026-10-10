"""NOVA — NLP Pipeline Classifier (Orchestrator).

Combines preprocessing, language detection, intent classification,
and entity extraction into a single pipeline.
"""

from __future__ import annotations

from typing import Any
import re

import structlog

from app.nlp.preprocessing import normalize_text, clean_for_intent
from app.nlp.language_detection import detect_language
from app.nlp.intent import classify_intent, classify_intent_with_llm, Intent
from app.nlp.entities import extract_entities
from app.schemas.chat import NLPResult
from app.tools.open_target import OpenTarget, classify_open_target

logger = structlog.get_logger(__name__)


async def analyze(text: str, use_llm_fallback: bool = True) -> NLPResult:
    """
    Run the full NLP pipeline on input text.

    Pipeline stages:
    1. Normalize text
    2. Detect language
    3. Classify intent (deterministic, then LLM fallback)
    4. Extract entities
    """
    # 1. Normalize
    normalized = normalize_text(text)
    if not normalized:
        return NLPResult(intent=Intent.UNKNOWN.value, confidence=0.0)

    # 2. Language detection
    language = detect_language(normalized)

    # 3. Intent classification
    cleaned = clean_for_intent(normalized)
    intent, confidence = classify_intent(cleaned)

    # If confidence is low and LLM is available, try LLM classification
    if confidence < 0.70 and use_llm_fallback:
        try:
            llm_intent, llm_confidence = await classify_intent_with_llm(normalized)
            if llm_confidence > confidence:
                intent = llm_intent
                confidence = llm_confidence
        except Exception as e:
            logger.debug("llm_fallback_skipped", error=str(e))

    # 4. Entity extraction
    entities = extract_entities(normalized)
    search_query = entities.get("browser_query")
    has_local_search_context = bool(
        re.search(r"\b(?:document|documents|pdf|file|files|folder|folders|uploaded)\b", normalized, re.I)
    )
    if search_query and not has_local_search_context:
        query_words = re.findall(r"[a-z0-9]+", str(search_query), re.I)
        query_is_question = bool(
            re.search(r"\?", normalized)
            or re.match(r"(?i)(?:what|who|where|when|why|how|which)\b", str(search_query).strip())
        )
        if len(query_words) > 1 or query_is_question or re.match(r"(?i)^(?:look\s+up|google)\b", normalized):
            intent = Intent.BROWSER_SEARCH
            confidence = 0.94
        else:
            intent = Intent.SEARCH_AMBIGUOUS
            confidence = 0.90
    explicit_site_request = bool(re.search(r"\b(?:website|site)\s*[.!?]?$", normalized, re.I))
    if entities.get("app_name"):
        entities["app_name"] = re.sub(
            r"\s+(?:website|site|app|application|program|browser)\s*$",
            "",
            str(entities["app_name"]),
            flags=re.I,
        ).strip()
    if intent == Intent.OPEN_APPLICATION and entities.get("app_name"):
        target = classify_open_target(str(entities["app_name"]))
        if target == OpenTarget.WEBSITE:
            intent = Intent.OPEN_AMBIGUOUS if explicit_site_request else Intent.OPEN_WEBSITE
        elif target == OpenTarget.AMBIGUOUS:
            intent = Intent.OPEN_AMBIGUOUS

    logger.info(
        "nlp_analysis_complete",
        intent=intent.value,
        confidence=round(confidence, 3),
        entity_count=len(entities),
        language=language,
    )

    return NLPResult(
        intent=intent.value,
        confidence=round(confidence, 4),
        entities=entities,
        language=language,
    )
