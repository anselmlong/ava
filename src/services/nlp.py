"""Natural-language extraction helpers.

These helpers use the LLM to extract structured data (JSON) from user messages.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime
from typing import Any, Optional

from src.config.logging import get_logger
from src.services.llm.gemini import get_gemini_service

logger = get_logger(__name__)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from LLM output."""
    raw = (text or "").strip()

    # Common model behavior: ```json ... ```
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")

    return json.loads(raw[start : end + 1])


@dataclass(frozen=True)
class GoalExtraction:
    title: str
    description: Optional[str]


@dataclass(frozen=True)
class ReminderExtraction:
    text: str
    schedule_text: str
    schedule_type: str
    date_local_iso: Optional[str]
    next_run_at_local: Optional[str]
    needs_clarification: bool
    clarification_question: Optional[str]


@dataclass(frozen=True)
class TimeFollowupExtraction:
    next_run_at_local: Optional[str]
    needs_clarification: bool
    clarification_question: Optional[str]


_JSON_SYSTEM_PROMPT = """You are a strict JSON extractor.

Return ONLY valid JSON. No markdown. No backticks. No extra keys.
"""


async def extract_goal(*, message_text: str) -> GoalExtraction:
    gemini = get_gemini_service()
    prompt = """Extract a single personal goal from the user message.

JSON schema:
{
  "title": "short goal title",
  "description": "optional longer description or null"
}

Rules:
- Title must be non-empty.
- Do not invent details.
"""

    response = await gemini.generate(
        message=prompt + "\n\nUser message:\n" + message_text,
        history=None,
        system_prompt=_JSON_SYSTEM_PROMPT,
    )

    data = _extract_json_object(response)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Goal title missing")

    description = data.get("description")
    if isinstance(description, str):
        description = description.strip() or None
    else:
        description = None

    return GoalExtraction(title=title, description=description)


async def extract_reminder(
    *,
    message_text: str,
    user_timezone: str,
    now_local_iso: str,
) -> ReminderExtraction:
    gemini = get_gemini_service()

    prompt = f"""Extract a reminder request.

Return JSON schema:
{{
  "text": "what to remind the user about",
  "schedule_text": "the schedule phrase as written (or normalized)",
  "schedule_type": "once"|"daily"|"weekly",
  "date_local_iso": "YYYY-MM-DD in the user's timezone"|null,
  "next_run_at_local": "ISO datetime in the user's timezone"|null,
  "needs_clarification": true|false,
  "clarification_question": "question to ask"|null
}}

Context:
- User timezone: {user_timezone}
- Current local datetime: {now_local_iso}

Rules:
- If the user gives a date like "tomorrow" but NO time, set needs_clarification=true and ask: "what time tomorrow?" (open-ended). In this case, set date_local_iso to the target date.
- If schedule is unclear for any reason, ask one concise open-ended question.
- If schedule_type is daily/weekly, next_run_at_local should be the next occurrence.
- Do not guess missing times.
"""

    response = await gemini.generate(
        message=prompt + "\n\nUser message:\n" + message_text,
        history=None,
        system_prompt=_JSON_SYSTEM_PROMPT,
    )

    data = _extract_json_object(response)

    text = (data.get("text") or "").strip()
    schedule_text = (data.get("schedule_text") or "").strip()
    schedule_type = (data.get("schedule_type") or "").strip()

    needs_clarification = bool(data.get("needs_clarification"))
    clarification_question = data.get("clarification_question")
    if isinstance(clarification_question, str):
        clarification_question = clarification_question.strip() or None
    else:
        clarification_question = None

    date_local_iso = data.get("date_local_iso")
    if isinstance(date_local_iso, str):
        date_local_iso = date_local_iso.strip() or None
    else:
        date_local_iso = None

    next_run_at_local = data.get("next_run_at_local")
    if isinstance(next_run_at_local, str):
        next_run_at_local = next_run_at_local.strip() or None
    else:
        next_run_at_local = None

    if not text:
        raise ValueError("Reminder text missing")
    if not schedule_text:
        schedule_text = message_text

    if schedule_type not in {"once", "daily", "weekly"}:
        raise ValueError("Invalid schedule_type")

    if needs_clarification and not clarification_question:
        clarification_question = "what time?"

    return ReminderExtraction(
        text=text,
        schedule_text=schedule_text,
        schedule_type=schedule_type,
        date_local_iso=date_local_iso,
        next_run_at_local=next_run_at_local,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
    )


async def extract_time_followup(
    *,
    message_text: str,
    user_timezone: str,
    date_local_iso: str,
) -> TimeFollowupExtraction:
    """Extract a concrete datetime for an existing local date."""

    gemini = get_gemini_service()
    prompt = f"""The user is answering a follow-up question asking for a time.

You must combine the provided local date with the user's time answer.

Return JSON schema:
{{
  "next_run_at_local": "ISO datetime in the user's timezone"|null,
  "needs_clarification": true|false,
  "clarification_question": "question to ask"|null
}}

Context:
- User timezone: {user_timezone}
- Target local date: {date_local_iso}

Rules:
- If the user provides a time (e.g. "3pm", "15:30"), return next_run_at_local.
- If the user does NOT provide a usable time, ask one open-ended question.
- Do not guess.
"""

    response = await gemini.generate(
        message=prompt + "\n\nUser message:\n" + message_text,
        history=None,
        system_prompt=_JSON_SYSTEM_PROMPT,
    )

    data = _extract_json_object(response)

    needs_clarification = bool(data.get("needs_clarification"))
    clarification_question = data.get("clarification_question")
    if isinstance(clarification_question, str):
        clarification_question = clarification_question.strip() or None
    else:
        clarification_question = None

    next_run_at_local = data.get("next_run_at_local")
    if isinstance(next_run_at_local, str):
        next_run_at_local = next_run_at_local.strip() or None
    else:
        next_run_at_local = None

    return TimeFollowupExtraction(
        next_run_at_local=next_run_at_local,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
    )


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("Datetime must include timezone offset")

    return parsed
