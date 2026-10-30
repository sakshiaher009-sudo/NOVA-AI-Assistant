"""NOVA — Settings, Notes, Reminders, Memory Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agent.memory import delete_memory, list_memories, store_memory
from app.database.database import get_db_session
from app.database.repositories import NoteRepo, ReminderRepo, SettingsRepo
from app.dependencies.auth import get_current_user_id
from app.schemas.analytics import (
    MemoryCreate,
    MemoryOut,
    NoteCreate,
    NoteOut,
    NoteUpdate,
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
    SettingUpdate,
)

router = APIRouter(tags=["settings"])


# ── Settings ──────────────────────────────────────────────────

@router.get("/api/settings")
async def get_settings_all(user_id: str = Depends(get_current_user_id)):
    async with get_db_session() as session:
        return await SettingsRepo.get_all(session, user_id=user_id)


@router.post("/api/settings")
async def update_setting(
    setting: SettingUpdate,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        await SettingsRepo.set(session, setting.key, setting.value, user_id=user_id)
        return {"status": "updated"}


# ── Notes ─────────────────────────────────────────────────────

@router.get("/api/notes", response_model=list[NoteOut])
async def list_notes(user_id: str = Depends(get_current_user_id)):
    async with get_db_session() as session:
        notes = await NoteRepo.list_all(session, user_id=user_id)
        return [NoteOut.model_validate(n) for n in notes]


@router.post("/api/notes", response_model=NoteOut)
async def create_note(
    note: NoteCreate,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        n = await NoteRepo.create(
            session,
            title=note.title,
            content=note.content,
            tags=note.tags,
            user_id=user_id,
        )
        return NoteOut.model_validate(n)


@router.put("/api/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: str,
    note: NoteUpdate,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        updated = await NoteRepo.update(
            session,
            note_id,
            title=note.title,
            content=note.content,
            tags=note.tags,
            user_id=user_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Note not found")
        n = await NoteRepo.get(session, note_id, user_id=user_id)
        return NoteOut.model_validate(n)


@router.delete("/api/notes/{note_id}")
async def remove_note(
    note_id: str,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        deleted = await NoteRepo.delete(session, note_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"status": "deleted"}


# ── Reminders ─────────────────────────────────────────────────

@router.get("/api/reminders", response_model=list[ReminderOut])
async def list_reminders(user_id: str = Depends(get_current_user_id)):
    async with get_db_session() as session:
        reminders = await ReminderRepo.list_all(session, user_id=user_id)
        return [ReminderOut.model_validate(r) for r in reminders]


@router.post("/api/reminders", response_model=ReminderOut)
async def create_reminder(
    reminder: ReminderCreate,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        r = await ReminderRepo.create(
            session,
            title=reminder.title,
            description=reminder.description,
            scheduled_at=reminder.scheduled_at,
            user_id=user_id,
        )
        return ReminderOut.model_validate(r)


@router.put("/api/reminders/{rem_id}", response_model=ReminderOut)
async def update_reminder(
    rem_id: str,
    reminder: ReminderUpdate,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        updated = await ReminderRepo.update(
            session,
            rem_id,
            title=reminder.title,
            description=reminder.description,
            scheduled_at=reminder.scheduled_at,
            status=reminder.status,
            user_id=user_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Reminder not found")
        r = await ReminderRepo.get(session, rem_id, user_id=user_id)
        return ReminderOut.model_validate(r)


@router.delete("/api/reminders/{rem_id}")
async def remove_reminder(
    rem_id: str,
    user_id: str = Depends(get_current_user_id),
):
    async with get_db_session() as session:
        deleted = await ReminderRepo.delete(session, rem_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"status": "deleted"}


# ── Memory ────────────────────────────────────────────────────

@router.get("/api/memory", response_model=list[MemoryOut])
async def get_memories(user_id: str = Depends(get_current_user_id)):
    memories = await list_memories(user_id=user_id)
    return memories


@router.post("/api/memory", response_model=dict)
async def add_memory(
    memory: MemoryCreate,
    user_id: str = Depends(get_current_user_id),
):
    mem_id = await store_memory(
        content=memory.content,
        category=memory.category,
        user_id=user_id,
    )
    return {"id": mem_id, "status": "stored"}


@router.delete("/api/memory/{mem_id}")
async def remove_memory(
    mem_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await delete_memory(mem_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}
