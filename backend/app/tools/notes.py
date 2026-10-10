"""NOVA — Notes Tool."""

from __future__ import annotations

from typing import Any

from app.database.database import get_db_session
from app.database.repositories import NoteRepo
from app.tools.base import BaseTool, ToolParameter, ToolResult


class CreateNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_note"

    @property
    def description(self) -> str:
        return "Save a note or piece of information for the user."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="title", type="string", description="Short title for the note"),
            ToolParameter(name="content", type="string", description="Note content", required=False, default=""),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        title = str(params.get("title", "")).strip()
        content = str(params.get("content", "")).strip()

        if not title:
            return ToolResult(success=False, error="Note title is required")

        async with get_db_session() as session:
            note = await NoteRepo.create(session, title=title, content=content)
            return ToolResult(
                success=True,
                result={"id": note.id, "title": note.title},
                display_text=f'Noted: "{title}"',
            )


class ListNotesTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_notes"

    @property
    def description(self) -> str:
        return "List all saved notes."

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        async with get_db_session() as session:
            notes = await NoteRepo.list_all(session)
            if not notes:
                return ToolResult(success=True, result=[], display_text="You have no saved notes.")

            items = [{"id": n.id, "title": n.title, "content": n.content} for n in notes]
            lines = [f"• {n.title}" for n in notes]
            return ToolResult(
                success=True,
                result=items,
                display_text=f"Your notes:\n" + "\n".join(lines),
            )


class DeleteNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "delete_note"

    @property
    def description(self) -> str:
        return "Delete a note by its ID or search by title."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Note ID or title to search for"),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, error="Please specify which note to delete")

        async with get_db_session() as session:
            # Try as ID first
            deleted = await NoteRepo.delete(session, query)
            if deleted:
                return ToolResult(success=True, display_text="Note deleted.")

            # Search by title
            notes = await NoteRepo.search(session, query)
            if notes:
                note = notes[0]
                await NoteRepo.delete(session, note.id)
                return ToolResult(success=True, display_text=f'Deleted note: "{note.title}"')

            return ToolResult(success=False, error=f"No note found matching '{query}'")
