"""NOVA — Backend Tests: Tools."""

import pytest
from types import SimpleNamespace

from app.tools.calculator import safe_calculate, CalculatorTool
from app.tools.time_tool import TimeTool
from app.tools.execute_terminal import ExecuteTerminalTool
from app.tools.open_application import OpenApplicationTool
from app.tools.open_website import OpenWebsiteTool
from app.tools.browser_search import BrowserSearchTool


class TestCalculator:
    def test_addition(self):
        assert safe_calculate("2 + 3") == 5.0

    def test_subtraction(self):
        assert safe_calculate("10 - 4") == 6.0

    def test_multiplication(self):
        assert safe_calculate("987 * 43") == 987 * 43

    def test_division(self):
        assert safe_calculate("100 / 4") == 25.0

    def test_complex_expression(self):
        assert safe_calculate("(2 + 3) * 4") == 20.0

    def test_power(self):
        assert safe_calculate("2 ** 10") == 1024.0

    def test_caret_power(self):
        assert safe_calculate("2 ^ 10") == 1024.0

    def test_negative(self):
        assert safe_calculate("-5 + 3") == -2.0

    def test_float(self):
        assert abs(safe_calculate("3.14 * 2") - 6.28) < 0.001

    def test_division_by_zero(self):
        with pytest.raises(ValueError, match="Division by zero"):
            safe_calculate("1 / 0")

    def test_large_exponent_rejected(self):
        with pytest.raises(ValueError):
            safe_calculate("2 ** 10000")

    def test_trailing_equals(self):
        assert safe_calculate("5 + 3 =") == 8.0

    def test_trailing_question(self):
        assert safe_calculate("5 + 3?") == 8.0


@pytest.mark.asyncio
class TestCalculatorTool:
    async def test_execute(self):
        tool = CalculatorTool()
        result = await tool.safe_execute({"expression": "2 + 2"})
        assert result.success
        assert result.result == 4.0

    async def test_missing_expression(self):
        tool = CalculatorTool()
        result = await tool.safe_execute({})
        assert not result.success


@pytest.mark.asyncio
class TestTimeTool:
    async def test_execute(self):
        tool = TimeTool()
        result = await tool.safe_execute({})
        assert result.success
        assert "time" in result.result
        assert "date" in result.result


@pytest.mark.asyncio
class TestExecuteTerminalTool:
    async def test_safe_command_captures_output_and_exit_code(self):
        result = await ExecuteTerminalTool().safe_execute({"command": "python3 --version"})
        assert result.success
        assert result.result["exit_code"] == 0
        assert result.result["stdout"] or result.result["stderr"]

    async def test_risky_command_requires_confirmation(self):
        result = await ExecuteTerminalTool().safe_execute({"command": "rm -rf /tmp/example"})
        assert not result.success
        assert result.result["confirmation_required"] is True


@pytest.mark.asyncio
class TestOpenApplicationTool:
    async def test_valid_application_name(self, monkeypatch):
        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.open_application.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        result = await OpenApplicationTool().safe_execute({"app_name": "Calculator"})

        assert result.success
        assert result.result["app"] == "Calculator"

    async def test_invalid_application_name_is_rejected(self):
        result = await OpenApplicationTool().safe_execute({"app_name": "Definitely Not An App"})

        assert not result.success
        assert result.result["reason"] == "not_whitelisted"

    async def test_unsafe_input_is_rejected_without_launching(self, monkeypatch):
        launch_attempted = False

        async def fake_create_subprocess_exec(*args, **kwargs):
            nonlocal launch_attempted
            launch_attempted = True
            raise AssertionError("unsafe input must not reach the native launcher")

        monkeypatch.setattr(
            "app.tools.open_application.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        result = await OpenApplicationTool().safe_execute({"app_name": "Terminal; rm -rf /"})

        assert not result.success
        assert result.result["reason"] == "unsafe_input"
        assert not launch_attempted

    async def test_successful_launch_handling(self, monkeypatch):
        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.open_application.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        result = await OpenApplicationTool().safe_execute({"app_name": "Safari"})

        assert result.success
        assert result.result == {"app": "Safari", "requested": "Safari"}

    async def test_failed_launch_handling(self, monkeypatch):
        async def fake_communicate():
            return b"", b"Unable to find application named Safari"

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate, returncode=1)

        monkeypatch.setattr(
            "app.tools.open_application.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        result = await OpenApplicationTool().safe_execute({"app_name": "Safari"})

        assert not result.success
        assert result.result["reason"] == "not_installed"


@pytest.mark.asyncio
class TestOpenWebsiteTool:
    async def test_known_website(self, monkeypatch):
        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.open_website.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await OpenWebsiteTool().safe_execute({"site_name": "Google"})
        assert result.success
        assert result.result["url"] == "https://www.google.com"

    async def test_unknown_website_rejected(self):
        result = await OpenWebsiteTool().safe_execute({"site_name": "unknown.example"})
        assert not result.success
        assert result.result["reason"] == "invalid_name"

    async def test_curated_website_mapping(self, monkeypatch):
        calls = []

        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            calls.append(args)
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.open_website.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await OpenWebsiteTool().safe_execute({"site_name": "Claude"})
        assert result.success
        assert result.result["url"] == "https://claude.ai"
        assert calls == [("open", "https://claude.ai")]

    async def test_unmapped_name_uses_safe_slug_fallback(self, monkeypatch):
        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.open_website.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await OpenWebsiteTool().safe_execute({"site_name": "Example Site"})
        assert result.success
        assert result.result["url"] == "https://www.example-site.com"

    async def test_nonsense_name_is_rejected(self):
        result = await OpenWebsiteTool().safe_execute({"site_name": "asdf!!!123"})
        assert not result.success
        assert result.result["reason"] == "invalid_name"

    async def test_raw_url_is_never_passed_to_browser(self, monkeypatch):
        launch_attempted = False

        async def fake_create_subprocess_exec(*args, **kwargs):
            nonlocal launch_attempted
            launch_attempted = True
            raise AssertionError("raw URLs must not reach the browser launcher")

        monkeypatch.setattr(
            "app.tools.open_website.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await OpenWebsiteTool().safe_execute({"site_name": "https://evil.example"})
        assert not result.success
        assert not launch_attempted


@pytest.mark.asyncio
class TestBrowserSearchTool:
    @pytest.mark.parametrize(
        "query",
        ["C++ vs Python?", "50% off deals", "a & b", "user@example.com"],
    )
    async def test_special_characters_are_encoded(self, monkeypatch, query):
        calls = []

        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            calls.append(args)
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.browser_search.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await BrowserSearchTool().safe_execute({"query": query})
        assert result.success
        assert calls[0][0] == "open"
        assert query not in calls[0][1]
        assert "https://www.google.com/search?q=" in calls[0][1]

    async def test_reuses_website_url_validation(self, monkeypatch):
        async def fake_communicate():
            return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            return _completed_process(args, fake_communicate)

        monkeypatch.setattr(
            "app.tools.browser_search.asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        result = await BrowserSearchTool().safe_execute({"query": "machine learning"})
        assert result.success
        assert result.result["url"].startswith("https://")

    async def test_raw_url_query_is_rejected(self):
        result = await BrowserSearchTool().safe_execute(
            {"query": "https://evil.example"}
        )
        assert not result.success
        assert result.result["reason"] == "invalid_query"


def _completed_process(args, communicate, returncode=0):
    return SimpleNamespace(returncode=returncode, args=args, communicate=communicate)
