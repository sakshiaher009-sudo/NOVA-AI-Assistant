"""NOVA — Time Tool.

Phase 2 safe test tool: returns the current local system time and date.
No side effects, no external network calls, no file I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.tools.base import BaseTool, ToolResult


class TimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return (
            "Get the current local date and time. "
            "Use this when the user asks what time it is, what today's date is, "
            "or any question about the current time or date."
        )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")  # "3:45 PM" not "03:45 PM"
        date_str = now.strftime("%A, %B %d, %Y")
        return ToolResult(
            success=True,
            result={
                "time": time_str,
                "date": date_str,
                "iso": now.isoformat(),
                "timestamp": int(now.timestamp()),
                "hour_24": now.strftime("%H:%M"),
            },
            display_text=f"It's {time_str} on {date_str}.",
        )
