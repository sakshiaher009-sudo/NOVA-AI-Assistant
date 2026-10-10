"""Deterministic classification for natural-language open requests."""

from __future__ import annotations

from enum import Enum

from app.tools.open_application import _APP_WHITELIST
from app.tools.open_website import is_known_website


class OpenTarget(str, Enum):
    APPLICATION = "application"
    WEBSITE = "website"
    AMBIGUOUS = "ambiguous"


def classify_open_target(name: str) -> OpenTarget:
    key = name.strip().lower()
    is_application = key in _APP_WHITELIST
    is_website = is_known_website(key)
    if is_application and is_website:
        return OpenTarget.AMBIGUOUS
    if is_website:
        return OpenTarget.WEBSITE
    if is_application:
        return OpenTarget.APPLICATION
    return OpenTarget.AMBIGUOUS

