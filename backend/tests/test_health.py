"""NOVA — Backend Tests: Health & Config."""

import pytest
from unittest.mock import AsyncMock, patch


def test_settings_default():
    """Test default settings load correctly."""
    from app.config import Settings
    s = Settings()
    assert s.app_name == "NOVA"
    assert s.backend_port == 8000
    assert s.ollama_model == "llama3.2:1b"


def test_settings_cors_parsing():
    """Test CORS origins are parsed correctly."""
    from app.config import Settings
    s = Settings(cors_origins="http://a.com, http://b.com")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_settings_extensions():
    """Test allowed extensions parsing."""
    from app.config import Settings
    s = Settings(allowed_extensions="pdf,txt,md")
    assert s.allowed_extension_list == ["pdf", "txt", "md"]


def test_settings_upload_bytes():
    """Test max upload bytes calculation."""
    from app.config import Settings
    s = Settings(max_upload_mb=10)
    assert s.max_upload_bytes == 10 * 1024 * 1024
