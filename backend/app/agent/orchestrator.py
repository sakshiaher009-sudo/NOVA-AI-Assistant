"""NOVA — Agent Orchestrator.

Central coordination: NLP analysis → Agent Router → tool/RAG decision
→ LLM reasoning → response.

Phase 2 additions:
  - Formal AgentState machine (idle → thinking → executing → responding → idle)
  - AgentRouter: clean separation of routing logic
  - Tool-result → LLM synthesis loop: tool output is fed back into the LLM
    so the final response is always natural language, not raw JSON.
  - agent_state exposed in ChatResponse for frontend consumption.
  - Comprehensive error handling covering invalid tools, tool failures,
    LLM failures, and Ollama connectivity issues.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional, Callable, Awaitable

import structlog

from app.config import get_settings
from app.nlp.classifier import analyze as nlp_analyze
from app.nlp.intent import Intent, classify_intent
from app.llm import ollama_client
from app.llm.schemas import LLMMessage
from app.agent.context import build_context
from app.agent.conversation_state import (
    ConversationState,
    build_conversation_state,
    load_conversation_state,
)
from app.agent.prompts import (
    get_system_prompt,
    build_rag_prompt,
    build_summary_prompt,
    build_synthesis_prompt,
)
from app.agent.router import (
    is_tool_call,
    is_rag_call,
    is_internal_call,
    allows_llm_tool_calls,
    route_description,
)
from app.agent.states import AgentState
from app.agent.tool_registry import (
    get_tool_for_intent,
    init_tools,
    get_tool,
    get_tools_schema,
)
from app.agent.planner import Plan, create_plan, plan_from_tool_calls
from app.agent.task_context import TaskContext
from app.agent.response import format_tool_response, format_error_response
from app.agent.memory import search_memories, store_memory
from app.database.database import get_db_session
from app.database.repositories import (
    ConversationRepo,
    MessageRepo,
    ToolExecutionRepo,
)
from app.schemas.chat import ChatResponse, NLPResult, PlanStatus, ToolResult

logger = structlog.get_logger(__name__)

_initialized = False


def _is_fast_path(nlp_result: NLPResult) -> bool:
    """Deterministic fast path for sub-millisecond simple queries."""
    return nlp_result.intent in ("GET_TIME", "CALCULATE") and nlp_result.confidence > 0.90


async def _conversation_context(
    message: str, conversation_id: Optional[str]
) -> tuple[str, list[Any], list[dict]]:
    async with get_db_session() as session:
        if conversation_id:
            conv = await ConversationRepo.get(session, conversation_id)
            if not conv:
                conv = await ConversationRepo.create(session, title=_generate_title(message))
        else:
            conv = await ConversationRepo.create(session, title=_generate_title(message))
        messages = await MessageRepo.get_by_conversation(session, conv.id)
    history = [{"role": item.role, "content": item.content} for item in messages]
    return conv.id, messages, history


def _pending_clarification(messages: list[Any]) -> Optional[dict[str, str]]:
    if not messages or messages[-1].role != "assistant" or not messages[-1].entities_json:
        return None
    try:
        state = json.loads(messages[-1].entities_json)
    except (TypeError, json.JSONDecodeError):
        return None
    pending = state.get("pending_clarification")
    if (
        isinstance(pending, dict)
        and isinstance(pending.get("original_name"), str)
        and pending.get("awaiting") in {
            "app_or_website",
            "search_target",
            "search_query_for_google",
            "search_query_for_youtube",
            "gmail_followup",
        }
    ):
        return pending
    return None


def _resolve_clarification_reply(
    message: str, pending: dict[str, str]
) -> Optional[NLPResult]:
    reply = message.strip().lower()
    if pending["awaiting"] in {
        "search_query_for_google",
        "search_query_for_youtube",
    }:
        unrelated_intent, confidence = classify_intent(message)
        if confidence >= 0.85 and unrelated_intent in {
            Intent.GET_TIME,
            Intent.CALCULATE,
            Intent.OPEN_APPLICATION,
            Intent.OPEN_WEBSITE,
            Intent.CREATE_NOTE,
            Intent.CREATE_REMINDER,
        }:
            return None
        query = re.sub(r"^\s*(?:search|look\s+up|google)\s+", "", message.strip(), flags=re.I)
        if not query:
            return None
        return NLPResult(
            intent=Intent.BROWSER_SEARCH.value,
            confidence=1.0,
            entities={"browser_query": query},
            language="en",
        )
    if pending["awaiting"] == "gmail_followup":
        unrelated_intent, confidence = classify_intent(message)
        if confidence >= 0.85 and unrelated_intent in {
            Intent.GET_TIME,
            Intent.CALCULATE,
            Intent.OPEN_APPLICATION,
            Intent.OPEN_WEBSITE,
            Intent.CREATE_NOTE,
            Intent.CREATE_REMINDER,
        }:
            return None
        return NLPResult(
            intent=Intent.FOLLOWUP_ACKNOWLEDGEMENT.value,
            confidence=1.0,
            entities={"followup_answer": message.strip()},
            language="en",
        )
    if pending["awaiting"] == "search_target" and re.search(
        r"\b(?:web|browser|internet|google)\b", reply
    ):
        intent = Intent.BROWSER_SEARCH.value
        entities = {"browser_query": pending["original_name"]}
    elif pending["awaiting"] == "search_target" and re.search(
        r"\b(?:document|file|local)\b", reply
    ):
        intent = Intent.DOCUMENT_SEARCH.value
        entities = {"topic": pending["original_name"]}
    elif re.search(r"\b(?:website|site|browser)\b", reply):
        intent = Intent.OPEN_WEBSITE.value
        entities = {"app_name": pending["original_name"]}
    elif re.search(r"\b(?:app|application|program)\b", reply):
        intent = Intent.OPEN_APPLICATION.value
        entities = {"app_name": pending["original_name"]}
    else:
        intent = Intent.OPEN_AMBIGUOUS.value
        entities = {"app_name": pending["original_name"]}
    return NLPResult(
        intent=intent,
        confidence=1.0,
        entities=entities,
        language="en",
    )


def _website_followup_state(tool_result: Optional[ToolResult]) -> Optional[dict[str, str]]:
    if not tool_result or not tool_result.success or not isinstance(tool_result.result, dict):
        return None
    site_name = str(tool_result.result.get("site_name", "")).strip().lower()
    if site_name == "google":
        return {"awaiting": "search_query_for_google", "original_name": "Google"}
    if site_name == "youtube":
        return {"awaiting": "search_query_for_youtube", "original_name": "YouTube"}
    if site_name == "gmail":
        return {"awaiting": "gmail_followup", "original_name": "Gmail"}
    return None


async def _ensure_initialized():
    global _initialized
    if not _initialized:
        init_tools()
        _initialized = True


async def _relevant_conversation_memory(state: ConversationState) -> list[dict]:
    """Load only bounded memory relevant to the current conversation topic."""
    if not state.current_topic:
        return []
    try:
        return await search_memories(state.current_topic)
    except Exception as exc:
        logger.warning("conversation_memory_lookup_failed", error=str(exc))
        return []


async def process_message(
    message: str,
    conversation_id: Optional[str] = None,
    is_voice: bool = False,
) -> ChatResponse:
    """
    Process a user message through the full agent pipeline.

    Pipeline:
      1. NLP Analysis (intent + entities)
      2. Agent Router → decides: tool call / RAG / internal / conversation
      3. If tool call → execute tool → synthesize via LLM
      4. If conversation → LLM direct
      5. Save to DB, return ChatResponse with agent_state
    """
    await _ensure_initialized()
    total_start = time.perf_counter()

    # ── 1. Resolve conversation continuation before NLP ────────────────────────
    agent_state = AgentState.THINKING
    conversation_id, conversation_messages, conversation_history = await _conversation_context(
        message, conversation_id
    )
    previous_state = load_conversation_state(conversation_messages)
    pending = _pending_clarification(conversation_messages)
    logger.info(
        "clarification_state_checked",
        conversation_id=conversation_id,
        pending=pending,
        reply=message if pending else None,
    )
    nlp_result = _resolve_clarification_reply(message, pending) if pending else None
    if nlp_result is None:
        nlp_result = await nlp_analyze(message)
    intent = nlp_result.intent
    current_state = build_conversation_state(
        message,
        intent,
        nlp_result.confidence,
        nlp_result.entities,
        previous=previous_state,
    )

    logger.info(
        "agent_routing",
        intent=intent,
        confidence=nlp_result.confidence,
        route=route_description(nlp_result),
    )

    # ── 2. Save the current user message ────────────────────────────────────────
    async with get_db_session() as session:
        user_msg = await MessageRepo.create(
            session,
            conversation_id=conversation_id,
            role="user",
            content=message,
            intent=nlp_result.intent,
            confidence=nlp_result.confidence,
            entities=nlp_result.entities if nlp_result.entities else None,
            is_voice=is_voice,
        )

    # ── 3. Get conversation history for context ────────────────────────────────
    history = conversation_history

    # ── 4. Route & Execute ─────────────────────────────────────────────────────
    tool_result_schema: Optional[ToolResult] = None
    plan_status: PlanStatus | None = None
    response_text = ""
    llm_start = time.perf_counter()
    llm_duration_ms = 0
    planned_task: Optional[Plan] = None
    pending_for_response: Optional[dict[str, str]] = None

    try:
        if current_state.missing_information:
            response_text = (
                f"I need a little more information. What is the "
                f"{current_state.missing_information[0]}?"
            )
            agent_state = AgentState.RESPONDING
        elif intent in (Intent.OPEN_AMBIGUOUS.value, Intent.SEARCH_AMBIGUOUS.value):
            pending_for_response = {
                "original_name": nlp_result.entities.get(
                    "app_name", nlp_result.entities.get("browser_query", message)
                ),
                "awaiting": (
                    "app_or_website"
                    if intent == Intent.OPEN_AMBIGUOUS.value
                    else "search_target"
                ),
            }
            if intent == Intent.OPEN_AMBIGUOUS.value:
                response_text = (
                    f"Do you mean the {pending_for_response['original_name']} "
                    "application or its website?"
                )
            else:
                response_text = (
                    f"Should I search the web or your local documents/files for "
                    f"{pending_for_response['original_name']}?"
                )
            agent_state = AgentState.RESPONDING
        elif intent in (
            Intent.OPEN_APPLICATION.value,
            Intent.OPEN_WEBSITE.value,
            Intent.BROWSER_SEARCH.value,
        ):
            agent_state = AgentState.EXECUTING
            response_text, tool_result_schema = await _handle_tool_intent(
                intent, message, nlp_result, history, synthesize=False
            )
            pending_for_response = _website_followup_state(tool_result_schema)
            if pending_for_response:
                if pending_for_response["awaiting"].startswith("search_query"):
                    response_text = (
                        f"I've opened {pending_for_response['original_name']} — "
                        "what would you like to search for?"
                    )
                else:
                    response_text = (
                        "I've opened Gmail — is there a specific email or contact "
                        "you're looking for?"
                    )
            elif (
                intent == Intent.BROWSER_SEARCH.value
                and tool_result_schema
                and tool_result_schema.success
            ):
                query = nlp_result.entities.get("browser_query", message)
                response_text = f"Done. I searched for {query}."
            agent_state = AgentState.RESPONDING
        elif intent == Intent.FOLLOWUP_ACKNOWLEDGEMENT.value:
            response_text = (
                "I understand. I don't have an email-search action yet, "
                "but you can continue using Gmail to look for it."
            )
            agent_state = AgentState.RESPONDING
        elif _is_fast_path(nlp_result):
            # ── Fast path for deterministic simple queries (e.g. GET_TIME, CALCULATE) ──
            agent_state = AgentState.EXECUTING
            response_text, tool_result_schema = await _handle_tool_intent(
                intent, message, nlp_result, history, synthesize=False
            )
            agent_state = AgentState.RESPONDING
        else:
            # ── Native LLM Tool-Calling Path ──
            agent_state = AgentState.THINKING
            relevant_memory = await _relevant_conversation_memory(current_state)
            relevant_tool_result = None
            if current_state.unresolved_references and current_state.previous_tool_result is not None:
                relevant_tool_result = json.dumps(current_state.previous_tool_result, default=str)
            context = build_context(
                history,
                conversation_state=current_state,
                current_message=message,
                relevant_memory=relevant_memory,
                relevant_tool_result=relevant_tool_result,
                include_tools=False,
            )
            context.append(LLMMessage(role="user", content=message))
            tools_schema = get_tools_schema() if allows_llm_tool_calls(nlp_result) else None

            llm_start = time.perf_counter()
            llm_resp = await ollama_client.chat(context, tools=tools_schema, temperature=0.5)
            llm_duration_ms = int((time.perf_counter() - llm_start) * 1000)

            if llm_resp.tool_calls and allows_llm_tool_calls(nlp_result):
                # The LLM autonomously decided which tool(s) to call
                agent_state = AgentState.PLANNING
                planned_task = plan_from_tool_calls(message, llm_resp.tool_calls)
                if not planned_task:
                    planned_task = create_plan(message)

                if planned_task:
                    response_text, tool_result_schema, plan_status = await _handle_planned_task(
                        planned_task, message, history
                    )
                    agent_state = (
                        AgentState.COMPLETED
                        if plan_status.status == "completed"
                        else (
                            AgentState.WAITING_FOR_USER
                            if plan_status.status == "waiting_for_user"
                            else AgentState.FAILED
                        )
                    )
                else:
                    response_text = llm_resp.content or format_error_response("general")
                    agent_state = AgentState.RESPONDING
            elif is_rag_call(nlp_result):
                # RAG path when LLM answers without direct tool_calls
                agent_state = AgentState.RESPONDING
                response_text = await _handle_rag_intent(intent, message, nlp_result, history)
            elif is_internal_call(nlp_result):
                # Internal handlers (memory, system status)
                agent_state = AgentState.RESPONDING
                if intent == Intent.SEARCH_MEMORY.value:
                    response_text = await _handle_memory_search(message)
                elif intent == Intent.SYSTEM_STATUS.value:
                    response_text = await _handle_system_status()
            elif is_tool_call(nlp_result) and not llm_resp.content.strip():
                # Fallback to registered tool handler if model produced no output and no tool_calls
                agent_state = AgentState.EXECUTING
                response_text, tool_result_schema = await _handle_tool_intent(
                    intent, message, nlp_result, history
                )
                agent_state = AgentState.RESPONDING
            else:
                agent_state = AgentState.RESPONDING
                response_text = llm_resp.content

    except ConnectionError:
        agent_state = AgentState.ERROR
        response_text = format_error_response("ollama_unavailable")
    except ValueError as e:
        agent_state = AgentState.ERROR
        logger.warning("agent_invalid_tool", error=str(e))
        response_text = format_error_response("general")
    except Exception as e:
        agent_state = AgentState.ERROR
        logger.error("agent_processing_error", error=str(e), intent=intent)
        response_text = format_error_response("general")

    # Preserve task outcome states so the existing UI can observe Phase 4 work.
    final_state = agent_state if planned_task else (
        AgentState.IDLE if agent_state != AgentState.ERROR else AgentState.ERROR
    )

    total_latency = int((time.perf_counter() - total_start) * 1000)

    # ── 5. Save assistant response ─────────────────────────────────────────────
    async with get_db_session() as session:
        current_state.pending_action = (
            pending_for_response.get("awaiting") if pending_for_response else None
        )
        current_state.previous_tool = tool_result_schema.tool_name if tool_result_schema else None
        current_state.previous_tool_result = (
            tool_result_schema.result if tool_result_schema else None
        )
        assistant_msg = await MessageRepo.create(
            session,
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            intent=intent,
            entities={
                "pending_clarification": pending_for_response,
                "conversation_state": current_state.model_dump(),
            },
            tool_name=tool_result_schema.tool_name if tool_result_schema else None,
            tool_result=tool_result_schema.model_dump() if tool_result_schema else None,
            latency_ms=total_latency,
            llm_duration_ms=llm_duration_ms,
            is_voice=is_voice,
        )

        # Update conversation title if it's the first exchange
        if len(history) == 0:
            await ConversationRepo.update_title(session, conversation_id, _generate_title(message))

    return ChatResponse(
        message_id=assistant_msg.id,
        conversation_id=conversation_id,
        response=response_text,
        nlp=nlp_result,
        tool=tool_result_schema,
        latency_ms=total_latency,
        llm_duration_ms=llm_duration_ms,
        agent_state=final_state.value,
        plan=plan_status,
    )


async def process_message_stream(
    message: str,
    conversation_id: Optional[str] = None,
    is_voice: bool = False,
) -> AsyncGenerator[dict[str, Any], None]:
    """Process user message yielding SSE events as tokens and tool status updates stream."""
    await _ensure_initialized()
    total_start = time.perf_counter()

    # 1. State: Thinking
    yield {"type": "state", "agent_state": AgentState.THINKING.value}

    conversation_id, conversation_messages, conversation_history = await _conversation_context(
        message, conversation_id
    )
    previous_state = load_conversation_state(conversation_messages)
    pending = _pending_clarification(conversation_messages)
    logger.info(
        "clarification_state_checked",
        conversation_id=conversation_id,
        pending=pending,
        reply=message if pending else None,
    )
    nlp_result = _resolve_clarification_reply(message, pending) if pending else None
    if nlp_result is None:
        nlp_result = await nlp_analyze(message)
    intent = nlp_result.intent
    current_state = build_conversation_state(
        message,
        intent,
        nlp_result.confidence,
        nlp_result.entities,
        previous=previous_state,
    )

    # 2. Save current user message
    async with get_db_session() as session:
        await MessageRepo.create(
            session,
            conversation_id=conversation_id,
            role="user",
            content=message,
            intent=nlp_result.intent,
            confidence=nlp_result.confidence,
            entities=nlp_result.entities if nlp_result.entities else None,
            is_voice=is_voice,
        )

    yield {"type": "init", "conversation_id": conversation_id}

    # 3. Context
    history = conversation_history

    response_text = ""
    tool_result_schema: Optional[ToolResult] = None
    plan_status: Optional[PlanStatus] = None
    pending_for_response: Optional[dict[str, str]] = None

    try:
        if current_state.missing_information:
            response_text = (
                f"I need a little more information. What is the "
                f"{current_state.missing_information[0]}?"
            )
            yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
        elif intent in (Intent.OPEN_AMBIGUOUS.value, Intent.SEARCH_AMBIGUOUS.value):
            pending_for_response = {
                "original_name": nlp_result.entities.get(
                    "app_name", nlp_result.entities.get("browser_query", message)
                ),
                "awaiting": (
                    "app_or_website"
                    if intent == Intent.OPEN_AMBIGUOUS.value
                    else "search_target"
                ),
            }
            if intent == Intent.OPEN_AMBIGUOUS.value:
                response_text = (
                    f"Do you mean the {pending_for_response['original_name']} "
                    "application or its website?"
                )
            else:
                response_text = (
                    f"Should I search the web or your local documents/files for "
                    f"{pending_for_response['original_name']}?"
                )
            yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
        elif intent in (
            Intent.OPEN_APPLICATION.value,
            Intent.OPEN_WEBSITE.value,
            Intent.BROWSER_SEARCH.value,
        ):
            yield {"type": "state", "agent_state": AgentState.EXECUTING.value}
            response_text, tool_result_schema = await _handle_tool_intent(
                intent, message, nlp_result, history, synthesize=False
            )
            pending_for_response = _website_followup_state(tool_result_schema)
            if pending_for_response:
                if pending_for_response["awaiting"].startswith("search_query"):
                    response_text = (
                        f"I've opened {pending_for_response['original_name']} — "
                        "what would you like to search for?"
                    )
                else:
                    response_text = (
                        "I've opened Gmail — is there a specific email or contact "
                        "you're looking for?"
                    )
            elif (
                intent == Intent.BROWSER_SEARCH.value
                and tool_result_schema
                and tool_result_schema.success
            ):
                query = nlp_result.entities.get("browser_query", message)
                response_text = f"Done. I searched for {query}."
            yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
        elif intent == Intent.FOLLOWUP_ACKNOWLEDGEMENT.value:
            response_text = (
                "I understand. I don't have an email-search action yet, "
                "but you can continue using Gmail to look for it."
            )
            yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
        elif _is_fast_path(nlp_result):
            yield {"type": "state", "agent_state": AgentState.EXECUTING.value}
            response_text, tool_result_schema = await _handle_tool_intent(
                intent, message, nlp_result, history, synthesize=False
            )
            yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
            words = response_text.split(" ")
            for idx, word in enumerate(words):
                token = word if idx == 0 else f" {word}"
                yield {"type": "token", "token": token}
                await asyncio.sleep(0.01)
        else:
            relevant_memory = await _relevant_conversation_memory(current_state)
            relevant_tool_result = None
            if current_state.unresolved_references and current_state.previous_tool_result is not None:
                relevant_tool_result = json.dumps(current_state.previous_tool_result, default=str)
            context = build_context(
                history,
                conversation_state=current_state,
                current_message=message,
                relevant_memory=relevant_memory,
                relevant_tool_result=relevant_tool_result,
                include_tools=False,
            )
            context.append(LLMMessage(role="user", content=message))
            tools_schema = get_tools_schema() if allows_llm_tool_calls(nlp_result) else None

            llm_resp = await ollama_client.chat(context, tools=tools_schema, temperature=0.5)
            if llm_resp.tool_calls and allows_llm_tool_calls(nlp_result):
                yield {"type": "state", "agent_state": AgentState.PLANNING.value}
                planned_task = plan_from_tool_calls(message, llm_resp.tool_calls)
                if not planned_task:
                    planned_task = create_plan(message)

                if planned_task:
                    yield {"type": "state", "agent_state": AgentState.EXECUTING.value}
                    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

                    async def on_state_cb(s: str):
                        await queue.put({"type": "state", "agent_state": s})

                    worker = asyncio.create_task(
                        _handle_planned_task(planned_task, message, history, on_state=on_state_cb)
                    )
                    while not worker.done():
                        try:
                            evt = await asyncio.wait_for(queue.get(), timeout=0.03)
                            yield evt
                        except asyncio.TimeoutError:
                            pass
                    while not queue.empty():
                        yield queue.get_nowait()
                    response_text, tool_result_schema, plan_status = await worker

                    yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                    words = response_text.split(" ")
                    for idx, word in enumerate(words):
                        token = word if idx == 0 else f" {word}"
                        yield {"type": "token", "token": token}
                        await asyncio.sleep(0.01)
                else:
                    response_text = llm_resp.content
                    yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                    yield {"type": "token", "token": response_text}
            elif is_rag_call(nlp_result):
                yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                response_text = await _handle_rag_intent(intent, message, nlp_result, history)
                words = response_text.split(" ")
                for idx, word in enumerate(words):
                    token = word if idx == 0 else f" {word}"
                    yield {"type": "token", "token": token}
                    await asyncio.sleep(0.01)
            elif is_internal_call(nlp_result):
                yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                if intent == Intent.SEARCH_MEMORY.value:
                    response_text = await _handle_memory_search(message)
                elif intent == Intent.SYSTEM_STATUS.value:
                    response_text = await _handle_system_status()
                yield {"type": "token", "token": response_text}
            elif is_tool_call(nlp_result) and not llm_resp.content.strip():
                yield {"type": "state", "agent_state": AgentState.EXECUTING.value}
                queue_tool: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

                async def on_state_tool_cb(s: str):
                    await queue_tool.put({"type": "state", "agent_state": s})

                worker_tool = asyncio.create_task(
                    _handle_tool_intent(intent, message, nlp_result, history, on_state=on_state_tool_cb)
                )
                while not worker_tool.done():
                    try:
                        evt = await asyncio.wait_for(queue_tool.get(), timeout=0.03)
                        yield evt
                    except asyncio.TimeoutError:
                        pass
                while not queue_tool.empty():
                    yield queue_tool.get_nowait()
                response_text, tool_result_schema = await worker_tool

                yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                words = response_text.split(" ")
                for idx, word in enumerate(words):
                    token = word if idx == 0 else f" {word}"
                    yield {"type": "token", "token": token}
                    await asyncio.sleep(0.01)
            else:
                yield {"type": "state", "agent_state": AgentState.RESPONDING.value}
                chunks = []
                async for chunk in ollama_client.chat_stream(context, temperature=0.5):
                    chunks.append(chunk)
                    yield {"type": "token", "token": chunk}
                response_text = "".join(chunks)

    except Exception as e:
        logger.error("stream_error", error=str(e))
        response_text = format_error_response("general")
        yield {"type": "token", "token": response_text}

    total_latency = int((time.perf_counter() - total_start) * 1000)

    # Save assistant message in DB
    async with get_db_session() as session:
        current_state.pending_action = (
            pending_for_response.get("awaiting") if pending_for_response else None
        )
        current_state.previous_tool = tool_result_schema.tool_name if tool_result_schema else None
        current_state.previous_tool_result = (
            tool_result_schema.result if tool_result_schema else None
        )
        assistant_msg = await MessageRepo.create(
            session,
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            intent=intent,
            entities={
                "pending_clarification": pending_for_response,
                "conversation_state": current_state.model_dump(),
            },
            tool_name=tool_result_schema.tool_name if tool_result_schema else None,
            tool_result=tool_result_schema.model_dump() if tool_result_schema else None,
            latency_ms=total_latency,
            is_voice=is_voice,
        )
        if len(history) == 0:
            await ConversationRepo.update_title(session, conversation_id, _generate_title(message))

    yield {
        "type": "done",
        "message_id": assistant_msg.id,
        "conversation_id": conversation_id,
        "response": response_text,
        "latency_ms": total_latency,
        "agent_state": AgentState.IDLE.value,
        "plan": plan_status.model_dump() if plan_status else None,
        "tool_name": tool_result_schema.tool_name if tool_result_schema else None,
        "tool": tool_result_schema.model_dump() if tool_result_schema else None,
        "intent": intent,
    }


# ── Tool Handler ───────────────────────────────────────────────────────────────

async def _handle_tool_intent(
    intent: str,
    message: str,
    nlp_result: NLPResult,
    history: list[dict],
    synthesize: bool = True,
    on_state: Optional[Callable[[str], Awaitable[None]]] = None,
) -> tuple[str, Optional[ToolResult]]:
    """
    Handle intents that map to tool execution.

    Flow:
      1. Resolve the tool from the registry (raises ValueError if not found)
      2. Build parameters from NLP entities
      3. Execute the tool via safe_execute (never raises)
      4. Feed the tool result back into the LLM for a natural response (skipped on fast path)
      5. Log the execution to the DB
    """
    tool = get_tool_for_intent(intent)
    if not tool:
        logger.warning("tool_not_found_for_intent", intent=intent)
        raise ValueError(f"No tool registered for intent: {intent}")

    # Build tool parameters from NLP entities
    params = _build_tool_params(intent, message, nlp_result)

    # Execute tool (never raises — wraps all exceptions in ToolResult)
    result = await tool.safe_execute(params)

    # Log tool execution
    try:
        async with get_db_session() as session:
            await ToolExecutionRepo.create(
                session,
                tool_name=tool.name,
                input_data=params,
                output_data={"result": str(result.result), "display": result.display_text},
                success=result.success,
                error_message=result.error,
            )
    except Exception as e:
        logger.warning("tool_execution_log_failed", error=str(e))

    # ── Phase 2: Synthesize a natural response using LLM with Self-Verification ──────
    if not synthesize:
        # Fast path bypasses LLM latency completely
        response_text = format_tool_response(tool.name, result)
    elif result.success:
        if on_state:
            await on_state(AgentState.VERIFYING.value)
        is_valid, reason = await _verify_tool_result(message, tool.name, result.result)
        if is_valid:
            if on_state:
                await on_state(AgentState.RESPONDING.value)
            response_text = await _synthesize_tool_response(
                original_message=message,
                tool_name=tool.name,
                tool_result=result.result,
                display_text=result.display_text,
                history=history,
            )
        else:
            if on_state:
                await on_state(AgentState.RESPONDING.value)
            response_text = await _handle_verification_failure(
                user_message=message,
                tool_name=tool.name,
                tool_result=result.result,
                reason=reason,
                history=history,
            )
    else:
        response_text = format_tool_response(tool.name, result)

    tool_schema = ToolResult(
        tool_name=tool.name,
        success=result.success,
        result=result.result,
        error=result.error,
    )

    return response_text, tool_schema


async def _verify_tool_result(
    user_message: str,
    tool_name: str,
    tool_result: Any,
) -> tuple[bool, str]:
    """
    Judge whether the tool output validly answers the user's intent using an LLM judgment call.
    Fails open (returns is_valid=True) if the LLM call fails or times out.
    """
    if tool_result is None:
        return False, "Tool returned no output."

    try:
        settings = get_settings()
        display = (
            tool_result.get("display_text")
            if isinstance(tool_result, dict) and "display_text" in tool_result
            else json.dumps(tool_result, default=str)[:500]
        )
        prompt = (
            "Analyze if the tool output correctly answers the user request.\n"
            f'Request: "{user_message}"\n'
            f"Tool output: {display}\n\n"
            "Respond with JSON:\n"
            "{\n"
            '  "is_valid": <true if output answers request, false if wrong/empty/unrelated>,\n'
            '  "reason": "<explanation>"\n'
            "}"
        )
        resp = await ollama_client.generate(
            prompt,
            model=settings.ollama_model,
            temperature=0.0,
            format="json",
        )
        data = json.loads(resp)
        if "is_valid" in data:
            return bool(data["is_valid"]), str(data.get("reason", ""))
    except Exception as e:
        logger.warning("verification_llm_failed_fail_open", error=str(e))
        return True, "Verification skipped (fail open)"

    return True, "Valid"


async def _handle_verification_failure(
    user_message: str,
    tool_name: str,
    tool_result: Any,
    reason: str,
    history: list[dict],
) -> str:
    """Generate an honest failure explanation or clarification instead of false success."""
    prompt = (
        f"The user asked: \"{user_message}\"\n"
        f"We executed `{tool_name}`, but the result was insufficient or unsuccessful: {reason}\n"
        f"Raw data: {tool_result}\n\n"
        f"Generate an honest, polite, and helpful response explaining that the request could not be completed "
        f"as expected, why it failed, and ask a clarifying question or suggest next steps. "
        f"Do NOT pretend the action succeeded."
    )
    try:
        context = build_context(history)
        context.append(LLMMessage(role="user", content=prompt))
        resp = await ollama_client.chat(context, temperature=0.3)
        if resp.content.strip():
            return resp.content.strip()
    except Exception:
        pass
    return f"I ran {tool_name}, but couldn't obtain the expected result ({reason}). Could you please clarify or provide more details?"


async def _handle_planned_task(
    plan: Plan,
    message: str,
    history: list[dict],
    on_state: Optional[Callable[[str], Awaitable[None]]] = None,
) -> tuple[str, ToolResult | None, PlanStatus]:
    """Execute a validated plan one step at a time and stop on new ambiguity."""
    context = TaskContext(original_goal=plan.goal, plan=plan, state=AgentState.EXECUTING.value)
    last_tool_result: ToolResult | None = None

    while (step := context.next_step()) is not None:
        tool = get_tool(step.tool)
        if not tool:
            step.status = "failed"
            step.error = f"The planned tool {step.tool} is unavailable."
            context.state = AgentState.FAILED.value
            break

        step.status = "executing"
        params = context.resolve_parameters(step.parameters)
        if any(value is None for value in params.values()):
            step.status = "waiting_for_user"
            step.error = "A previous step did not provide the value required to continue."
            context.state = AgentState.WAITING_FOR_USER.value
            break

        validation_error = tool.validate_input(params)
        if validation_error:
            step.status = "failed"
            step.error = validation_error
            context.state = AgentState.FAILED.value
            break

        result = await tool.safe_execute(params)
        last_tool_result = ToolResult(
            tool_name=tool.name, success=result.success, result=result.result, error=result.error
        )
        step.result = result.result
        step.error = result.error

        if not result.success:
            step.status = "failed"
            context.state = AgentState.FAILED.value
            break

        # File selection is a planning decision, not a guess. Stop for clarification.
        if tool.name == "file_search":
            files = (result.result or {}).get("files", [])
            if len(files) != 1:
                step.status = "waiting_for_user" if len(files) > 1 else "failed"
                context.state = (
                    AgentState.WAITING_FOR_USER.value if len(files) > 1 else AgentState.FAILED.value
                )
                break

        step.status = "completed"
        context.completed_steps.append(step.id)
        context.observations[step.id] = result.result

    if context.state == AgentState.EXECUTING.value:
        context.state = AgentState.VERIFYING.value
        plan.status = "completed"
        fallback = f"Completed {len(context.completed_steps)} planned steps for: {plan.goal}"
    elif context.state == AgentState.WAITING_FOR_USER.value:
        plan.status = "waiting_for_user"
        fallback = "I found multiple possible matches. Please choose the file or project you want me to inspect."
    else:
        plan.status = "failed"
        fallback = "I could not complete the planned task because one of the steps failed."

    if last_tool_result and last_tool_result.success:
        if on_state:
            await on_state(AgentState.VERIFYING.value)
        is_valid, reason = await _verify_tool_result(message, last_tool_result.tool_name, last_tool_result.result)
        if is_valid:
            if on_state:
                await on_state(AgentState.RESPONDING.value)
            response = await _synthesize_tool_response(
                original_message=message,
                tool_name="multi_step_task",
                tool_result={
                    "goal": plan.goal,
                    "completed_steps": context.completed_steps,
                    "observations": context.observations,
                    "status": plan.status,
                },
                display_text=fallback,
                history=history,
            )
        else:
            plan.status = "failed"
            context.state = AgentState.FAILED.value
            if on_state:
                await on_state(AgentState.RESPONDING.value)
            response = await _handle_verification_failure(
                user_message=message,
                tool_name=last_tool_result.tool_name,
                tool_result=last_tool_result.result,
                reason=reason,
                history=history,
            )
    else:
        response = fallback

    plan_status = PlanStatus(
        goal=plan.goal,
        status=plan.status,
        current_step=next((s.id for s in plan.steps if s.status in {"executing", "waiting_for_user"}), None),
        completed_steps=context.completed_steps,
        total_steps=len(plan.steps),
    )
    return response, last_tool_result, plan_status


async def _synthesize_tool_response(
    original_message: str,
    tool_name: str,
    tool_result: Any,
    display_text: Optional[str],
    history: list[dict],
) -> str:
    """Feed tool output back into the LLM with few-shot synthesis prompt."""
    fallback = display_text or str(tool_result)

    try:
        context = build_context(history)
        synthesis_prompt = build_synthesis_prompt(
            original_message=original_message,
            tool_name=tool_name,
            tool_result=tool_result,
            display_text=display_text,
        )
        context.append(LLMMessage(role="user", content=synthesis_prompt))

        response = await ollama_client.chat(context, temperature=0.5)
        synthesized = response.content.strip()

        if synthesized:
            return synthesized

    except ConnectionError:
        logger.warning("tool_synthesis_ollama_unavailable", tool=tool_name)
    except Exception as e:
        logger.warning("tool_synthesis_failed", tool=tool_name, error=str(e))

    return fallback


# ── Other handlers (unchanged) ─────────────────────────────────────────────────

def _build_tool_params(intent: str, message: str, nlp_result: NLPResult) -> dict[str, Any]:
    """Build tool parameters from NLP entities and message."""
    entities = nlp_result.entities
    params: dict[str, Any] = {}

    if intent == "CALCULATE":
        params["expression"] = entities.get("math_expression", message)

    elif intent == "GET_TIME":
        # get_current_time requires no parameters
        pass

    elif intent == "CREATE_NOTE":
        task = entities.get("task", "")
        if not task:
            import re
            match = re.search(
                r"(?:remember\s+(?:that|to)\s+|note\s+(?:that|down)\s+|save\s+(?:a\s+)?note\s+)(.+)",
                message, re.I,
            )
            task = match.group(1).strip().rstrip(".") if match else message
        params["title"] = task
        params["content"] = task

    elif intent == "DELETE_NOTE":
        import re
        match = re.search(r"(?:delete|remove|clear)\s+(?:the\s+|a\s+|my\s+)?note\s+(?:about\s+)?(.+)", message, re.I)
        params["query"] = match.group(1).strip() if match else message

    elif intent == "CREATE_REMINDER":
        task = entities.get("task", "")
        if not task:
            import re
            match = re.search(
                r"(?:remind\s+me\s+(?:to\s+|about\s+)|reminder\s+(?:to\s+|for\s+))(.+?)(?:\s+(?:at|on|by|tomorrow|today)\b|$)",
                message, re.I,
            )
            task = match.group(1).strip().rstrip(".") if match else message
        params["title"] = task
        params["date"] = entities.get("date")
        params["time"] = entities.get("time") or entities.get("relative_time")

    elif intent in ("DOCUMENT_SEARCH", "DOCUMENT_SUMMARY"):
        params["query"] = entities.get("topic", message)

    elif intent == "OPEN_APPLICATION":
        params["app_name"] = entities.get("app_name", message)

    elif intent == "OPEN_WEBSITE":
        params["site_name"] = entities.get("app_name", message)

    elif intent == "BROWSER_SEARCH":
        params["query"] = entities.get("browser_query", message)

    elif intent == "FILE_SEARCH":
        params["query"] = entities.get("search_query", entities.get("topic", message))

    elif intent == "READ_FILE":
        params["file_path"] = entities.get("file_path", message)

    elif intent == "EXECUTE_TERMINAL":
        params["command"] = entities.get("command", message)

    return params


async def _handle_rag_intent(
    intent: str, message: str, nlp_result: NLPResult, history: list[dict]
) -> str:
    """Handle document search / summary via RAG."""
    try:
        from app.rag.retriever import search_documents

        query = nlp_result.entities.get("topic", message)
        results = await search_documents(query)

        if not results:
            return "I couldn't find relevant information in your uploaded documents."

        if intent == "DOCUMENT_SUMMARY":
            context_text = "\n\n".join(r["content"] for r in results[:3])
            prompt = build_summary_prompt(results[0].get("document_name", "document"), context_text)
        else:
            prompt = build_rag_prompt(query, results)

        context = build_context(history)
        context.append(LLMMessage(role="user", content=prompt))

        response = await ollama_client.chat(context)
        return response.content

    except ImportError:
        return "The document search system is not configured. Please upload documents first."
    except Exception as e:
        logger.error("rag_error", error=str(e))
        return "I encountered an error searching your documents. Please try again."


async def _handle_memory_search(message: str) -> str:
    """Search through stored memories."""
    from app.agent.memory import search_memories

    results = await search_memories(message)
    if not results:
        return "I don't have any stored memories matching that query."

    lines = [f"• {m['content']}" for m in results[:5]]
    return "Here's what I remember:\n" + "\n".join(lines)


async def _handle_system_status() -> str:
    """Return system status information."""
    from app.llm.model_manager import get_status

    status = await get_status()
    parts = [
        f"**NOVA System Status**",
        f"- Ollama: {'✅ Running' if status['ollama_running'] else '❌ Not running'}",
        f"- Model: {status['model_configured']} ({'✅ Available' if status['model_available'] else '❌ Not found'})",
        f"- Models installed: {', '.join(status['models_installed']) or 'None'}",
    ]
    return "\n".join(parts)


async def _handle_llm_conversation(message: str, history: list[dict]) -> str:
    """Handle general conversation via LLM."""
    context = build_context(history)
    context.append(LLMMessage(role="user", content=message))

    response = await ollama_client.chat(context)
    return response.content


def _generate_title(message: str) -> str:
    """Generate a conversation title from the first message."""
    title = message.strip()[:60]
    if len(message) > 60:
        title += "..."
    return title
