"""NOVA — File Search Tool (Phase 3).

Searches for files by name within a curated set of safe user directories.
Never searches system directories, never modifies files, never reads content
(that is the job of read_file). Safely handles permission errors.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult

# ── Safe search directories ────────────────────────────────────────────────────
# Only these directories (and their subdirectories) are searched.
# System directories, /etc, /usr, /bin, etc. are never touched.
_SAFE_DIRS: list[Path] = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path.home() / "Movies",
    Path.home() / "Music",
    Path.home() / "Projects",
    Path.home() / "Code",
    Path.home() / "Developer",
    Path.home() / "Sites",
    Path.home() / "repos",
    Path.home() / "Workspace",
]

# Filter to only directories that actually exist
_SEARCH_ROOTS: list[Path] = [d for d in _SAFE_DIRS if d.is_dir()]

# File types that are considered readable (shown in results)
_TEXT_EXTENSIONS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown", ".rst",
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".htm", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".csv", ".tsv",
    ".sh", ".bash", ".zsh",
    ".xml", ".svg",
    ".pdf", ".docx", ".doc", ".odt",
    ".ipynb",
})

# Max results to return
_MAX_RESULTS = 20

# Max depth to recurse into directories
_MAX_DEPTH = 6


def _search_dir(root: Path, query: str, depth: int = 0) -> list[dict]:
    """Recursively search a directory for files matching the query."""
    if depth > _MAX_DEPTH:
        return []

    results: list[dict] = []
    try:
        for entry in root.iterdir():
            try:
                if entry.is_symlink():
                    continue  # Skip symlinks to avoid traversal loops
                if entry.is_file():
                    # Match against filename (case-insensitive)
                    if query in entry.name.lower():
                        results.append({
                            "path": str(entry),
                            "name": entry.name,
                            "size_bytes": entry.stat().st_size,
                            "extension": entry.suffix.lower(),
                            "is_text": entry.suffix.lower() in _TEXT_EXTENSIONS,
                        })
                elif entry.is_dir():
                    # Skip hidden dirs (e.g. .git, .venv, node_modules)
                    if entry.name.startswith(".") or entry.name in {
                        "node_modules", "__pycache__", ".venv", "venv",
                        "env", ".git", "build", "dist", ".next",
                    }:
                        continue
                    results.extend(_search_dir(entry, query, depth + 1))
            except PermissionError:
                continue  # Skip files/dirs we can't read
    except PermissionError:
        pass  # Skip directories we can't enter

    return results


class FileSearchTool(BaseTool):
    """Search for files by name within safe user directories."""

    @property
    def name(self) -> str:
        return "file_search"

    @property
    def description(self) -> str:
        return (
            "Search for files by name in the user's directories (Desktop, Documents, Downloads, etc.). "
            "Returns matching file paths. Does not modify files. "
            "Use this when the user asks to 'find', 'locate', or 'search for' a file."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="The filename or partial filename to search for, e.g. 'DBMS notes', 'resume.pdf'",
            )
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip().lower()
        if not query:
            return ToolResult(success=False, error="No search query provided.")

        if len(query) < 2:
            return ToolResult(
                success=False,
                error="Search query must be at least 2 characters.",
            )

        if not _SEARCH_ROOTS:
            return ToolResult(
                success=False,
                error="No accessible search directories found. Desktop, Documents, and Downloads directories were checked.",
            )

        # Collect all results from all search roots
        all_results: list[dict] = []
        for root in _SEARCH_ROOTS:
            found = _search_dir(root, query)
            all_results.extend(found)

        # Deduplicate by path
        seen_paths: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            if r["path"] not in seen_paths:
                seen_paths.add(r["path"])
                unique_results.append(r)

        # Sort: exact name matches first, then by path length (shorter = more specific)
        def sort_key(r: dict) -> tuple:
            exact = 0 if query == r["name"].lower().replace(r["extension"], "") else 1
            starts = 0 if r["name"].lower().startswith(query) else 1
            return (exact, starts, len(r["path"]))

        unique_results.sort(key=sort_key)
        limited = unique_results[:_MAX_RESULTS]

        if not limited:
            searched_dirs = [str(r) for r in _SEARCH_ROOTS]
            return ToolResult(
                success=True,
                result={"query": query, "count": 0, "files": [], "searched_in": searched_dirs},
                display_text=(
                    f"No files found matching '{query}' in your Desktop, Documents, "
                    f"Downloads, and other personal folders."
                ),
            )

        # Build summary for display
        paths_preview = [r["path"] for r in limited[:5]]
        total = len(unique_results)
        shown = len(limited)

        display = f"Found {total} file(s) matching '{query}':\n"
        for r in limited[:5]:
            size_kb = r["size_bytes"] / 1024
            display += f"  • {r['name']}  ({size_kb:.1f} KB)  —  {r['path']}\n"
        if total > 5:
            display += f"  … and {total - 5} more."

        return ToolResult(
            success=True,
            result={
                "query": query,
                "count": total,
                "shown": shown,
                "files": limited,
                "searched_in": [str(r) for r in _SEARCH_ROOTS],
            },
            display_text=display.strip(),
        )
