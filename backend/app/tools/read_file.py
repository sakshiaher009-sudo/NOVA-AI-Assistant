"""NOVA — Read File Tool (Phase 3).

Reads the content of a text or code file and returns it to the agent.
Supports common text/code/data formats. Enforces size limits and safe paths.
Never modifies the file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult
from app.tools.file_search import _SEARCH_ROOTS, _TEXT_EXTENSIONS

# ── Safety limits ──────────────────────────────────────────────────────────────
_MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB hard limit
_MAX_CHARS_RETURNED = 8_000        # Trim very large files for LLM context

# Extensions we'll actually read (subset of text extensions — no binaries)
_READABLE_EXTENSIONS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown", ".rst",
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".htm", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".csv", ".tsv",
    ".sh", ".bash", ".zsh",
    ".xml",
    ".ipynb",
    # No .pdf, .docx, .doc — those are binary and require parsers
})

# Encodings to try in order
_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def _is_safe_path(path: Path) -> bool:
    """Return True if path is within an allowed search root."""
    try:
        resolved = path.resolve()
        for root in _SEARCH_ROOTS:
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False
    except Exception:
        return False


def _read_with_fallback_encoding(path: Path) -> tuple[str, str]:
    """Try to read file with multiple encodings. Returns (content, encoding_used)."""
    for enc in _ENCODINGS:
        try:
            content = path.read_text(encoding=enc)
            return content, enc
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode file with any supported encoding.")


class ReadFileTool(BaseTool):
    """Read the content of a text or code file from a safe path."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the content of a text, code, or data file and return it. "
            "Supports .txt, .md, .py, .js, .ts, .json, .csv, .html, .css, .yaml, .sh, and more. "
            "Only reads files within the user's personal directories. Does not modify files."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="The absolute path to the file to read.",
            )
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raw_path = str(params.get("file_path", "")).strip()
        if not raw_path:
            return ToolResult(success=False, error="No file path provided.")

        path = Path(raw_path).expanduser()

        # ── Safety checks ──────────────────────────────────────────────────────
        if not path.exists():
            return ToolResult(
                success=False,
                error=f"File not found: {path}",
                result={"path": str(path), "reason": "not_found"},
                display_text=f"I couldn't find the file at: {path}",
            )

        if not path.is_file():
            return ToolResult(
                success=False,
                error=f"Not a file: {path}",
                result={"path": str(path), "reason": "not_a_file"},
            )

        if not _is_safe_path(path):
            return ToolResult(
                success=False,
                error="Access denied: this file is outside the permitted directories.",
                result={"path": str(path), "reason": "outside_safe_dirs"},
                display_text=(
                    "For safety, I can only read files from your Desktop, Documents, "
                    "Downloads, and other personal folders."
                ),
            )

        # ── Extension check ────────────────────────────────────────────────────
        ext = path.suffix.lower()
        if ext not in _READABLE_EXTENSIONS:
            return ToolResult(
                success=False,
                error=f"File type '{ext}' is not supported for reading.",
                result={
                    "path": str(path),
                    "extension": ext,
                    "reason": "unsupported_extension",
                    "supported": sorted(_READABLE_EXTENSIONS),
                },
                display_text=(
                    f"I can't read '{ext}' files directly. "
                    f"Supported formats include: {', '.join(sorted(_READABLE_EXTENSIONS)[:12])}…"
                ),
            )

        # ── Size check ─────────────────────────────────────────────────────────
        try:
            file_size = path.stat().st_size
        except PermissionError:
            return ToolResult(
                success=False,
                error="Permission denied reading file metadata.",
                result={"path": str(path), "reason": "permission_denied"},
            )

        if file_size > _MAX_FILE_SIZE_BYTES:
            size_kb = file_size / 1024
            return ToolResult(
                success=False,
                error=f"File too large ({size_kb:.0f} KB). Maximum is {_MAX_FILE_SIZE_BYTES // 1024} KB.",
                result={
                    "path": str(path),
                    "size_bytes": file_size,
                    "reason": "file_too_large",
                },
                display_text=(
                    f"That file is {size_kb:.0f} KB which is too large for me to read in full. "
                    f"I can handle files up to {_MAX_FILE_SIZE_BYTES // 1024} KB."
                ),
            )

        # ── Read the file ──────────────────────────────────────────────────────
        try:
            content, encoding = _read_with_fallback_encoding(path)
        except PermissionError:
            return ToolResult(
                success=False,
                error="Permission denied reading file.",
                result={"path": str(path), "reason": "permission_denied"},
            )
        except ValueError as e:
            return ToolResult(
                success=False,
                error=str(e),
                result={"path": str(path), "reason": "encoding_error"},
                display_text="I couldn't decode this file — it may be a binary file or use an unsupported encoding.",
            )

        # ── Trim if needed ─────────────────────────────────────────────────────
        truncated = len(content) > _MAX_CHARS_RETURNED
        if truncated:
            content_to_return = content[:_MAX_CHARS_RETURNED]
            notice = f"\n\n[Note: File truncated to {_MAX_CHARS_RETURNED} characters. Full file is {len(content)} characters.]"
            content_to_return += notice
        else:
            content_to_return = content

        line_count = content.count("\n") + 1
        size_kb = file_size / 1024

        return ToolResult(
            success=True,
            result={
                "path": str(path),
                "filename": path.name,
                "extension": ext,
                "size_bytes": file_size,
                "line_count": line_count,
                "encoding": encoding,
                "truncated": truncated,
                "content": content_to_return,
            },
            display_text=(
                f"Read '{path.name}' ({size_kb:.1f} KB, {line_count} lines):\n\n"
                f"{content_to_return[:500]}{'…' if len(content_to_return) > 500 else ''}"
            ),
        )
