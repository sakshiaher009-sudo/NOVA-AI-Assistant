"""NOVA — Open Application Tool (Phase 3).

Opens an installed desktop application on the local macOS machine.
Only whitelisted applications can be opened. This prevents arbitrary
program execution while still covering the most useful everyday apps.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult

# ── Application whitelist ──────────────────────────────────────────────────────
# Maps human-friendly names (and common aliases) to the exact macOS app name.
# The 'open -a <app_name>' command uses these exact strings.
_APP_WHITELIST: dict[str, str] = {
    # Editors & IDEs
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "sublime": "Sublime Text",
    "sublime text": "Sublime Text",
    "atom": "Atom",
    "xcode": "Xcode",
    "pycharm": "PyCharm",
    "intellij": "IntelliJ IDEA",
    "webstorm": "WebStorm",
    "cursor": "Cursor",
    "zed": "Zed",

    # Browsers
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
    "brave": "Brave Browser",
    "arc": "Arc",
    "edge": "Microsoft Edge",

    # Productivity
    "notion": "Notion",
    "obsidian": "Obsidian",
    "notes": "Notes",
    "reminders": "Reminders",
    "calendar": "Calendar",
    "mail": "Mail",
    "messages": "Messages",
    "facetime": "FaceTime",
    "contacts": "Contacts",
    "maps": "Maps",

    # Terminal & Dev tools
    "terminal": "Terminal",
    "iterm": "iTerm",
    "iterm2": "iTerm2",
    "warp": "Warp",
    "hyper": "Hyper",
    "docker": "Docker",
    "postman": "Postman",
    "insomnia": "Insomnia",
    "tableplus": "TablePlus",
    "dbeaver": "DBeaver",

    # Media
    "spotify": "Spotify",
    "music": "Music",
    "vlc": "VLC",
    "quicktime": "QuickTime Player",
    "photos": "Photos",
    "preview": "Preview",

    # Communication
    "slack": "Slack",
    "discord": "Discord",
    "zoom": "Zoom",
    "teams": "Microsoft Teams",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "signal": "Signal",
    "skype": "Skype",

    # Office / Docs
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "pages": "Pages",
    "numbers": "Numbers",
    "keynote": "Keynote",
    "libreoffice": "LibreOffice",
    "google docs": "Google Docs",

    # System
    "finder": "Finder",
    "activity monitor": "Activity Monitor",
    "system preferences": "System Preferences",
    "system settings": "System Settings",
    "app store": "App Store",
    "calculator": "Calculator",
    "clock": "Clock",
    "screen time": "Screen Time",
}


def _resolve_app_name(requested: str) -> tuple[str | None, list[str]]:
    """
    Resolve a user-provided app name to a whitelisted app name.

    Returns:
        (exact_match_or_None, list_of_partial_matches)
    """
    query = requested.strip().lower()

    # Exact match first
    if query in _APP_WHITELIST:
        return _APP_WHITELIST[query], []

    # Partial match — find all keys that contain the query
    partials = [
        _APP_WHITELIST[k]
        for k in _APP_WHITELIST
        if query in k or k in query
    ]
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_partials: list[str] = []
    for p in partials:
        if p not in seen:
            seen.add(p)
            unique_partials.append(p)

    if len(unique_partials) == 1:
        return unique_partials[0], []

    return None, unique_partials


class OpenApplicationTool(BaseTool):
    """Open a whitelisted desktop application using macOS 'open -a'."""

    @property
    def name(self) -> str:
        return "open_app"

    @property
    def description(self) -> str:
        return (
            "Open an installed desktop application on this Mac. "
            "Accepts common app names like 'VS Code', 'Chrome', 'Spotify', 'Terminal', etc. "
            "Only whitelisted applications can be opened."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="app_name",
                type="string",
                description="The name of the application to open, e.g. 'VS Code', 'Chrome', 'Spotify'",
            )
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        requested = str(params.get("app_name", "")).strip()
        if not requested:
            return ToolResult(success=False, error="No application name provided.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9 .-]*", requested, re.IGNORECASE):
            return ToolResult(
                success=False,
                error="Application name contains unsupported characters.",
                result={"requested": requested, "reason": "unsafe_input"},
            )

        # Resolve the app name against the whitelist
        resolved, partials = _resolve_app_name(requested)

        if resolved is None and not partials:
            known_apps = sorted(set(_APP_WHITELIST.values()))
            return ToolResult(
                success=False,
                error=f"'{requested}' is not in the list of apps I can open.",
                result={
                    "requested": requested,
                    "known_apps_sample": known_apps[:20],
                    "reason": "not_whitelisted",
                },
                display_text=(
                    f"I don't recognise '{requested}' as an app I'm allowed to open. "
                    f"Try one of: {', '.join(known_apps[:10])}…"
                ),
            )

        if resolved is None and len(partials) > 1:
            return ToolResult(
                success=False,
                error=f"Ambiguous app name '{requested}'.",
                result={"requested": requested, "matches": partials, "reason": "ambiguous"},
                display_text=(
                    f"I found several apps matching '{requested}': "
                    f"{', '.join(partials)}. Which one did you mean?"
                ),
            )

        app_to_open = resolved or partials[0]

        # Launch the app asynchronously via `open -a`
        try:
            proc = await asyncio.create_subprocess_exec(
                "open", "-a", app_to_open,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace").strip()
                # Common case: app not installed
                if "Unable to find application" in err_msg or "can't be opened" in err_msg:
                    return ToolResult(
                        success=False,
                        error=f"{app_to_open} does not appear to be installed.",
                        result={"app": app_to_open, "reason": "not_installed"},
                        display_text=f"I tried to open {app_to_open} but it doesn't seem to be installed on this Mac.",
                    )
                return ToolResult(
                    success=False,
                    error=err_msg or f"Failed to open {app_to_open}",
                    result={"app": app_to_open, "stderr": err_msg},
                )

            return ToolResult(
                success=True,
                result={"app": app_to_open, "requested": requested},
                display_text=f"Opening {app_to_open}…",
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Timed out trying to open {app_to_open}.",
                result={"app": app_to_open, "reason": "timeout"},
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="The 'open' command is not available. Are you on macOS?",
                result={"reason": "open_not_found"},
            )
