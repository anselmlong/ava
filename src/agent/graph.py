"""LangGraph-based agent execution.

This agent supports:
- Normal conversation (memory retrieval -> Gemini response -> memory write)
- Goal creation + listing
- Reminder creation + listing, including clarification follow-ups for missing times

We log a decision trace rather than chain-of-thought.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TypedDict, cast

from zoneinfo import ZoneInfo
from langgraph.graph import END, START, StateGraph

from src.config.logging import get_logger
from src.config.settings import settings
from src.db.repositories.conversation import ConversationRepository
from src.db.repositories.goal import GoalRepository
from src.db.repositories.reminder import ReminderRepository
from src.db.repositories.user import UserRepository
from src.services.goals import GoalService
from src.services.llm.gemini import get_gemini_service
from src.services.memory import MemoryService
from src.services.reminders import ReminderService

logger = get_logger(__name__)


class AgentState(TypedDict):
    session: Any
    user_id: int
    conversation_id: int
    message_text: str
    history: list[dict]

    intent: str
    route: str
    decision_trace: list[str]

    user_timezone: str
    conversation_context: dict

    memory_enabled: bool
    memory_context: str

    response_text: str


def _truncate_for_memory(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _format_dt_for_user(dt_utc: datetime, user_timezone: str) -> str:
    try:
        tz = ZoneInfo(user_timezone)
        local = dt_utc.astimezone(tz)
        return local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _detect_route(message_text: str) -> str:
    text = (message_text or "").strip().lower()

    if any(token in text for token in ["list my goals", "show my goals", "my goals"]):
        return "goals:list"
    if text in {"goals", "list goals"}:
        return "goals:list"

    if any(
        token in text
        for token in ["list my reminders", "show my reminders", "my reminders"]
    ):
        return "reminders:list"
    if text in {"reminders", "list reminders"}:
        return "reminders:list"

    # Heuristics for creation intents.
    if "remind" in text or "reminder" in text:
        return "reminders:create"

    if "goal" in text or text.startswith("i want to") or text.startswith("i wanna"):
        return "goals:create"

    return "conversation"


async def _load_context_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    conv_repo = ConversationRepository(state["session"])
    conversation = await conv_repo.get_by_id(state["conversation_id"])
    conversation_context = dict(conversation.context or {}) if conversation else {}

    user_repo = UserRepository(state["session"])
    user = await user_repo.get_by_id(state["user_id"])
    user_timezone = user.timezone if user else "UTC"

    pending_action = conversation_context.get("pending_action")
    if pending_action:
        trace.append("pending_action:present")

    return {
        "conversation_context": conversation_context,
        "user_timezone": user_timezone,
        "decision_trace": trace,
    }


async def _route_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    pending = state.get("conversation_context", {}).get("pending_action")
    if isinstance(pending, dict) and pending.get("awaiting") == "time":
        trace.append("route:reminder_time_followup")
        return {
            "route": "reminders:time_followup",
            "intent": "reminder_time_followup",
            "decision_trace": trace,
        }

    route = _detect_route(state["message_text"])
    trace.append(f"route:{route}")

    intent = "conversation"
    if route.startswith("goals:"):
        intent = "goals"
    elif route.startswith("reminders:"):
        intent = "reminders"

    return {"route": route, "intent": intent, "decision_trace": trace}


async def _retrieve_memory_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    if not (settings.memory_read_enabled and state["memory_enabled"]):
        trace.append("memory:skipped")
        return {"memory_context": "", "decision_trace": trace}

    try:
        memory_service = MemoryService(state["session"])
        recent_user_messages = [
            msg["content"] for msg in state["history"] if msg.get("role") == "user"
        ] + [state["message_text"]]

        memory_context = await memory_service.get_context_for_conversation(
            user_id=state["user_id"],
            recent_messages=recent_user_messages,
            max_memories=settings.memory_retrieval_top_k,
        )

        trace.append("memory:used" if memory_context else "memory:none")
        return {"memory_context": memory_context, "decision_trace": trace}
    except Exception as exc:
        logger.warning(
            "Agent memory retrieval failed",
            user_id=state.get("user_id"),
            error=str(exc),
        )
        trace.append("memory:error")
        return {"memory_context": "", "decision_trace": trace}


async def _generate_response_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])
    gemini = get_gemini_service()

    system_prompt: Optional[str] = None
    memory_context = state.get("memory_context")
    if memory_context:
        system_prompt = (
            gemini.system_prompt
            + "\n\n"
            + memory_context
            + "\n\nUse the relevant memories only if they help answer the user. If they seem unrelated, ignore them."
        )

    response_text = await gemini.generate(
        message=state["message_text"],
        history=state.get("history") or [],
        system_prompt=system_prompt,
    )

    trace.append("llm:generated")
    return {"response_text": response_text, "decision_trace": trace}


async def _write_memory_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    if not (settings.memory_write_enabled and state["memory_enabled"]):
        trace.append("memory_write:skipped")
        return {"decision_trace": trace}

    try:
        memory_service = MemoryService(state["session"])
        user_excerpt = _truncate_for_memory(state["message_text"], 1500)
        assistant_excerpt = _truncate_for_memory(state.get("response_text", ""), 1500)
        conversation_text = f"User: {user_excerpt}\nAssistant: {assistant_excerpt}"

        await memory_service.extract_and_store_facts(
            user_id=state["user_id"],
            conversation_text=conversation_text,
            conversation_id=state["conversation_id"],
        )
        trace.append("memory_write:ok")
    except Exception as exc:
        logger.warning(
            "Agent memory write failed",
            user_id=state.get("user_id"),
            error=str(exc),
        )
        trace.append("memory_write:error")

    return {"decision_trace": trace}


async def _create_goal_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    service = GoalService(state["session"])
    goal = await service.create_from_nl(
        user_id=state["user_id"],
        message_text=state["message_text"],
    )

    trace.append("tool:goal:create")

    response = f"✅ got it. i added a goal: *{goal.title}*"
    return {"response_text": response, "decision_trace": trace}


async def _list_goals_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    repo = GoalRepository(state["session"])
    goals = await repo.list_for_user(user_id=state["user_id"], include_inactive=True)

    trace.append("tool:goal:list")

    if not goals:
        return {
            "response_text": "you don’t have any goals yet.",
            "decision_trace": trace,
        }

    lines = ["*Your goals:*", ""]
    for goal in goals[:20]:
        lines.append(f"• *{goal.title}* — {goal.status}")

    return {"response_text": "\n".join(lines), "decision_trace": trace}


async def _create_reminder_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    service = ReminderService(state["session"])
    result = await service.create_from_nl(
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
        message_text=state["message_text"],
        user_timezone=state.get("user_timezone") or "UTC",
    )

    trace.append("tool:reminder:create")

    if result.clarification_question:
        return {"response_text": result.clarification_question, "decision_trace": trace}

    reminder = result.reminder
    if reminder and reminder.next_run_at:
        when = _format_dt_for_user(
            reminder.next_run_at, state.get("user_timezone") or "UTC"
        )
        return {
            "response_text": f"✅ ok. i’ll remind you ({when}) to: {reminder.text}",
            "decision_trace": trace,
        }

    return {"response_text": "✅ ok. reminder saved.", "decision_trace": trace}


async def _reminder_time_followup_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    pending = state.get("conversation_context", {}).get("pending_action")
    draft: dict[str, Any] = {}
    if isinstance(pending, dict):
        raw_draft = pending.get("draft")
        if isinstance(raw_draft, dict):
            draft = raw_draft

    service = ReminderService(state["session"])
    result = await service.continue_from_time_followup(
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
        message_text=state["message_text"],
        user_timezone=state.get("user_timezone") or "UTC",
        draft=draft,
    )

    trace.append("tool:reminder:time_followup")

    if result.clarification_question:
        return {"response_text": result.clarification_question, "decision_trace": trace}

    reminder = result.reminder
    if reminder and reminder.next_run_at:
        when = _format_dt_for_user(
            reminder.next_run_at, state.get("user_timezone") or "UTC"
        )
        return {
            "response_text": f"✅ ok. i’ll remind you ({when}) to: {reminder.text}",
            "decision_trace": trace,
        }

    return {"response_text": "✅ ok.", "decision_trace": trace}


async def _list_reminders_node(state: AgentState) -> dict:
    trace = list(state.get("decision_trace") or [])

    repo = ReminderRepository(state["session"])
    reminders = await repo.list_for_user(
        user_id=state["user_id"], include_inactive=True
    )

    trace.append("tool:reminder:list")

    if not reminders:
        return {
            "response_text": "you don’t have any reminders yet.",
            "decision_trace": trace,
        }

    lines = ["*Your reminders:*", ""]
    for reminder in reminders[:20]:
        when = (
            _format_dt_for_user(
                reminder.next_run_at, state.get("user_timezone") or "UTC"
            )
            if reminder.next_run_at
            else "(unscheduled)"
        )
        status = "active" if reminder.is_active else "inactive"
        lines.append(f"• {when} — {status} — {reminder.text}")

    return {"response_text": "\n".join(lines), "decision_trace": trace}


def _build_agent():
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("load_context", _load_context_node)
    graph.add_node("route", _route_node)

    graph.add_node("retrieve_memory", _retrieve_memory_node)
    graph.add_node("generate_response", _generate_response_node)
    graph.add_node("write_memory", _write_memory_node)

    graph.add_node("create_goal", _create_goal_node)
    graph.add_node("list_goals", _list_goals_node)
    graph.add_node("create_reminder", _create_reminder_node)
    graph.add_node("list_reminders", _list_reminders_node)
    graph.add_node("reminder_time_followup", _reminder_time_followup_node)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "route")

    def choose_next(state: AgentState) -> str:
        route = state.get("route")
        if route == "conversation":
            return "retrieve_memory"
        if route == "goals:create":
            return "create_goal"
        if route == "goals:list":
            return "list_goals"
        if route == "reminders:create":
            return "create_reminder"
        if route == "reminders:list":
            return "list_reminders"
        if route == "reminders:time_followup":
            return "reminder_time_followup"
        return "retrieve_memory"

    graph.add_conditional_edges("route", choose_next)

    graph.add_edge("retrieve_memory", "generate_response")
    graph.add_edge("generate_response", "write_memory")
    graph.add_edge("write_memory", END)

    graph.add_edge("create_goal", END)
    graph.add_edge("list_goals", END)
    graph.add_edge("create_reminder", END)
    graph.add_edge("list_reminders", END)
    graph.add_edge("reminder_time_followup", END)

    return graph.compile()


_agent = _build_agent()


async def run_agent_turn(
    *,
    session: Any,
    user_id: int,
    conversation_id: int,
    message_text: str,
    history: list[dict],
    memory_enabled: bool,
) -> str:
    """Run one agent turn and return the final response text."""

    started_at = datetime.now(timezone.utc)
    result = await _agent.ainvoke(
        cast(
            AgentState,
            {
                "session": session,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_text": message_text,
                "history": history,
                "intent": "conversation",
                "route": "conversation",
                "decision_trace": [],
                "user_timezone": "UTC",
                "conversation_context": {},
                "memory_enabled": memory_enabled,
                "memory_context": "",
                "response_text": "",
            },
        )
    )

    response_text = result.get("response_text") or ""

    logger.info(
        "Agent turn completed",
        user_id=user_id,
        ava_intent=result.get("intent"),
        ava_route=result.get("route"),
        ava_decision_trace=result.get("decision_trace"),
        duration_ms=int(
            (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        ),
        response_length=len(response_text),
    )

    return response_text
