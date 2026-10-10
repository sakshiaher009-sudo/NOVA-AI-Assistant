"""NOVA — Safe browser search tool."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote_plus

from app.tools.base import BaseTool, ToolParameter, ToolResult
from app.tools.open_website import validate_website_url


class BrowserSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "browser_search"

    @property
    def description(self) -> str:
        return "Search the web in Google using a user-provided search phrase."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="query", type="string", description="Search phrase, not a URL")]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query or "://" in query:
            return ToolResult(
                success=False,
                error="Browser search requires a plain search phrase, not a URL.",
                result={"reason": "invalid_query"},
            )

        url = f"https://www.google.com/search?q={quote_plus(query, safe='')}"
        if not validate_website_url(url):
            return ToolResult(
                success=False,
                error="The constructed search URL failed URL safety validation.",
                result={"reason": "invalid_url"},
            )

        try:
            process = await asyncio.create_subprocess_exec(
                "open",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
            stderr_text = stderr.decode(errors="replace").strip()
            if process.returncode != 0:
                return ToolResult(
                    success=False,
                    error=stderr_text or "The browser search failed to launch.",
                    result={"url": url, "returncode": process.returncode},
                )
            return ToolResult(
                success=True,
                result={"query": query, "url": url},
                display_text=f"Searching the web for {query}.",
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error="Timed out trying to launch the browser search.")
        except FileNotFoundError:
            return ToolResult(success=False, error="The 'open' command is not available.")
