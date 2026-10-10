"""Controlled terminal command tool for safe, non-destructive diagnostics."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult

_TIMEOUT_SECONDS = 10
_SAFE_COMMANDS = {
    "python", "python3", "node", "npm", "git", "pwd", "whoami", "which",
    "date", "uname", "sw_vers", "ls", "echo",
}
_RISKY_TERMS = {
    "rm", "rmdir", "mv", "cp", "chmod", "chown", "sudo", "su", "diskutil",
    "kill", "shutdown", "reboot", "curl", "wget", "ssh", "secret", "password",
}
_NEVER_ALLOWED_TERMS = {"sudo", "su", "secret", "password"}


def _command_is_allowed(command: str, confirmed: bool = False) -> tuple[bool, str | None]:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False, "The command could not be parsed safely."
    if not parts:
        return False, "No command provided."
    if any(token.lower() in _NEVER_ALLOWED_TERMS for token in parts):
        return False, "Privilege escalation and credential-related commands are never permitted."
    if any(token.lower() in _RISKY_TERMS for token in parts) and not confirmed:
        return False, "This command is potentially destructive or sensitive and requires explicit confirmation."
    if parts[0] not in _SAFE_COMMANDS and not confirmed:
        return False, f"For safety, only approved diagnostic commands can run automatically: {parts[0]} is not approved."
    if any(token in {"&&", "||", ";", "|", ">", ">>"} for token in parts):
        return False, "Shell chaining and redirection are not allowed."
    return True, None


class ExecuteTerminalTool(BaseTool):
    @property
    def name(self) -> str:
        return "execute_terminal"

    @property
    def description(self) -> str:
        return "Run an approved, non-destructive diagnostic terminal command and return stdout, stderr, and exit code."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="command", type="string", description="An approved diagnostic command."),
            ToolParameter(name="confirmed", type="boolean", description="Explicit confirmation for a blocked risky command.", required=False, default=False),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        command = str(params.get("command", "")).strip()
        confirmed = params.get("confirmed", False) is True
        allowed, reason = _command_is_allowed(command, confirmed=confirmed)
        if not allowed:
            return ToolResult(success=False, error=reason, result={"command": command, "confirmation_required": True}, display_text=reason)

        try:
            process = await asyncio.create_subprocess_exec(
                *shlex.split(command), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(success=False, error=f"Command timed out after {_TIMEOUT_SECONDS} seconds.", result={"command": command, "timeout_seconds": _TIMEOUT_SECONDS})
        except FileNotFoundError:
            return ToolResult(success=False, error="The requested command is not installed.", result={"command": command})

        output = {"command": command, "stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace"), "exit_code": process.returncode}
        return ToolResult(success=process.returncode == 0, result=output, error=None if process.returncode == 0 else output["stderr"].strip() or f"Command exited with code {process.returncode}.", display_text=f"$ {command}\n{output['stdout']}{output['stderr']}")