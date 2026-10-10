"""NOVA — Reminder Notification Scheduler."""

from __future__ import annotations

import asyncio
import platform
import subprocess
from typing import Optional

import structlog

from app.config import get_settings
from app.database.database import get_db_session
from app.database.repositories import ReminderRepo

logger = structlog.get_logger(__name__)

_scheduler_instance: Optional[ReminderScheduler] = None


class ReminderScheduler:
    """Background scheduler that polls for due reminders and displays desktop notifications."""

    def __init__(self, poll_interval_seconds: Optional[int] = None):
        settings = get_settings()
        self.poll_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else settings.reminder_poll_interval_seconds
        )
        self._scheduler = None
        self._is_running = False

    def start(self) -> None:
        """Start the background scheduler."""
        if self._is_running:
            return

        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            self._scheduler = AsyncIOScheduler()
            self._scheduler.add_job(
                self.check_due_reminders,
                "interval",
                seconds=self.poll_interval,
                id="check_due_reminders",
                replace_existing=True,
            )
            self._scheduler.start()
            self._is_running = True
            logger.info("reminder_scheduler_started", interval_seconds=self.poll_interval)
        except Exception as e:
            logger.error("reminder_scheduler_start_failed", error=str(e))

    def stop(self) -> None:
        """Stop the background scheduler."""
        if self._scheduler and self._is_running:
            try:
                self._scheduler.shutdown(wait=False)
                self._is_running = False
                logger.info("reminder_scheduler_stopped")
            except Exception as e:
                logger.warning("reminder_scheduler_stop_error", error=str(e))

    async def check_due_reminders(self) -> list[str]:
        """Poll database for due reminders, notify user, and mark completed."""
        processed_ids = []
        try:
            async with get_db_session() as session:
                pending = await ReminderRepo.get_pending(session)
                if not pending:
                    return []

                logger.info("due_reminders_found", count=len(pending))
                for rem in pending:
                    await self._send_notification(rem.title, rem.description or "")
                    await ReminderRepo.update(session, rem.id, status="completed")
                    processed_ids.append(rem.id)

            return processed_ids
        except Exception as e:
            logger.error("reminder_check_failed", error=str(e))
            return []

    async def _send_notification(self, title: str, description: str) -> None:
        """Deliver desktop notification."""
        logger.info("triggering_reminder_notification", title=title, description=description)

        if platform.system() == "Darwin":
            try:
                # Sanitize single/double quotes for osascript
                safe_title = title.replace('"', '\\"')
                safe_desc = description.replace('"', '\\"')
                script = f'display notification "{safe_desc}" with title "NOVA: {safe_title}"'

                proc = await asyncio.create_subprocess_exec(
                    "osascript",
                    "-e",
                    script,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
            except Exception as e:
                logger.warning("macos_notification_failed", error=str(e))
        else:
            # Fallback for non-macOS platforms
            logger.info("desktop_notification_logged", title=title, description=description)


def get_reminder_scheduler() -> ReminderScheduler:
    """Get or initialize singleton ReminderScheduler."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ReminderScheduler()
    return _scheduler_instance
