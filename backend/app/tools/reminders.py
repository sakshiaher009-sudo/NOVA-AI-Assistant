"""NOVA — Reminders Tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.database.database import get_db_session
from app.database.repositories import ReminderRepo
from app.nlp.entities import resolve_date, resolve_time
from app.tools.base import BaseTool, ToolParameter, ToolResult


class CreateReminderTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_reminder"

    @property
    def description(self) -> str:
        return "Create a reminder with an optional date/time."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="title", type="string", description="What to remind about"),
            ToolParameter(name="description", type="string", description="Additional details", required=False, default=""),
            ToolParameter(name="date", type="string", description="Date (e.g., 'tomorrow', '2024-12-25')", required=False),
            ToolParameter(name="time", type="string", description="Time (e.g., '7 PM', '19:00')", required=False),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        title = str(params.get("title", "")).strip()
        if not title:
            return ToolResult(success=False, error="Reminder title is required")

        description = str(params.get("description", "")).strip()

        # Resolve scheduled_at from date + time
        scheduled_at: Optional[datetime] = None
        date_str = params.get("date")
        time_str = params.get("time")

        if date_str:
            scheduled_at = resolve_date(str(date_str))

        if time_str and scheduled_at:
            resolved_time = resolve_time(str(time_str))
            if resolved_time:
                h, m = map(int, resolved_time.split(":"))
                scheduled_at = scheduled_at.replace(hour=h, minute=m)
        elif time_str and not scheduled_at:
            # Time without date → assume today
            resolved_time = resolve_time(str(time_str))
            if resolved_time:
                h, m = map(int, resolved_time.split(":"))
                scheduled_at = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)

        async with get_db_session() as session:
            reminder = await ReminderRepo.create(
                session, title=title, description=description, scheduled_at=scheduled_at
            )

            time_msg = ""
            if scheduled_at:
                time_msg = f" for {scheduled_at.strftime('%B %d at %I:%M %p')}"

            return ToolResult(
                success=True,
                result={"id": reminder.id, "title": reminder.title, "scheduled_at": str(scheduled_at)},
                display_text=f'Reminder set: "{title}"{time_msg}.',
            )
