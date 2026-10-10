"""NOVA — Backend Tests: Reminder Notification Scheduler."""

import pytest
from datetime import datetime, timedelta
from app.services.reminder_scheduler import ReminderScheduler, get_reminder_scheduler
from app.database.database import get_db_session
from app.database.repositories import ReminderRepo


class TestReminderScheduler:
    def test_scheduler_singleton(self):
        s1 = get_reminder_scheduler()
        s2 = get_reminder_scheduler()
        assert s1 is s2
        assert s1.poll_interval > 0

    @pytest.mark.asyncio
    async def test_due_reminder_processing_and_completion(self, monkeypatch):
        notifications_sent = []

        async def fake_notify(self, title: str, description: str):
            notifications_sent.append((title, description))

        monkeypatch.setattr(ReminderScheduler, "_send_notification", fake_notify)

        scheduler = ReminderScheduler(poll_interval_seconds=5)

        # Create 1 overdue reminder and 1 future reminder
        async with get_db_session() as session:
            overdue = await ReminderRepo.create(
                session,
                title="Buy oat milk",
                description="Organic please",
                scheduled_at=datetime.utcnow() - timedelta(minutes=10),
            )
            future = await ReminderRepo.create(
                session,
                title="Dentist tomorrow",
                description="Routine checkup",
                scheduled_at=datetime.utcnow() + timedelta(days=1),
            )
            overdue_id = overdue.id
            future_id = future.id

        # Trigger check_due_reminders
        processed = await scheduler.check_due_reminders()
        assert overdue_id in processed
        assert future_id not in processed
        assert any(n[0] == "Buy oat milk" for n in notifications_sent)

        # Verify statuses in database
        async with get_db_session() as session:
            overdue_db = await ReminderRepo.get(session, overdue_id)
            future_db = await ReminderRepo.get(session, future_id)
            assert overdue_db.status == "completed"
            assert overdue_db.completed_at is not None
            assert future_db.status == "pending"

            # Cleanup test records
            await ReminderRepo.delete(session, overdue_id)
            await ReminderRepo.delete(session, future_id)
