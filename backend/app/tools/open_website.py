"""NOVA — Safe known-website launcher."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

from app.tools.base import BaseTool, ToolParameter, ToolResult
from app.tools.site_mappings import WEBSITE_URLS


def website_url(name: str) -> str | None:
    normalized = name.strip().lower()
    if normalized in WEBSITE_URLS:
        return WEBSITE_URLS[normalized]
    if (
        not normalized
        or not re.fullmatch(r"[a-z][a-z0-9]*(?:[ -][a-z0-9]+)*", normalized)
        or not re.search(r"[a-z]", normalized)
    ):
        return None
    slug = re.sub(r"[\s-]+", "-", normalized)
    return f"https://www.{slug}.com"


def is_known_website(name: str) -> bool:
    return name.strip().lower() in WEBSITE_URLS


def validate_website_url(url: str) -> bool:
    if not url.startswith("https://") or any(
        banned in url.lower() for banned in ("file://", "javascript:", "data:")
    ):
        return False
    if any(char in url for char in (";", "|", "&", "`", "$", "\n", "\r")):
        return False
    return bool(re.fullmatch(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::\d+)?(?:/[^ ]*)?", url))


class OpenWebsiteTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_website"

    @property
    def description(self) -> str:
        return "Open a recognized or safely slugified website name in the default browser."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="site_name", type="string", description="A website name, not a URL")]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        site_name = str(params.get("site_name", "")).strip()
        url = website_url(site_name)
        if not url:
            return ToolResult(
                success=False,
                error=f"'{site_name}' is not a valid website name.",
                result={"site_name": site_name, "reason": "invalid_name"},
                )

        parsed = urlparse(url)
        if not validate_website_url(url) or parsed.scheme != "https" or not parsed.netloc:
            return ToolResult(
                success=False,
                error="The configured website URL is invalid.",
                result={"site_name": site_name, "reason": "invalid_url"},
            )

        try:
            process = await asyncio.create_subprocess_exec(
                "open",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
            stdout_text = stdout.decode(errors="replace").strip()
            stderr_text = stderr.decode(errors="replace").strip()
            if process.returncode != 0:
                return ToolResult(
                    success=False,
                    error=stderr_text or f"Failed to open {site_name}",
                    result={
                        "site_name": site_name,
                        "url": url,
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "returncode": process.returncode,
                    },
                )
            return ToolResult(
                success=True,
                result={"site_name": site_name, "url": url},
                display_text=f"Opening {site_name}…",
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Timed out trying to open {site_name}.")
        except FileNotFoundError:
            return ToolResult(success=False, error="The 'open' command is not available.")
