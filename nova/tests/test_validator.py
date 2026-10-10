"""Tests for nova.validator — CLEAR / UNCLEAR decision logic."""

from nova.config import NovaConfig
from nova.interfaces import Transcript, ValidationStatus
from nova.validator import validate


def _make_config(**overrides) -> NovaConfig:
    """Create a config with test defaults."""
    defaults = {
        "validator_min_confidence": 0.4,
        "validator_min_length": 2,
    }
    defaults.update(overrides)
    return NovaConfig(**defaults)


class TestValidatorClear:
    """Tests for transcripts that should pass validation."""

    def test_normal_text(self):
        t = Transcript(text="Hello, how are you?", confidence=0.9)
        result = validate(t, config=_make_config())
        assert result.is_clear

    def test_no_confidence(self):
        """Confidence = None should not trigger the low-confidence check."""
        t = Transcript(text="Hello world", confidence=None)
        result = validate(t, config=_make_config())
        assert result.is_clear

    def test_exactly_min_length(self):
        t = Transcript(text="Hi", confidence=0.9)
        result = validate(t, config=_make_config(validator_min_length=2))
        assert result.is_clear

    def test_exactly_min_confidence(self):
        t = Transcript(text="Hello", confidence=0.4)
        result = validate(t, config=_make_config(validator_min_confidence=0.4))
        assert result.is_clear


class TestValidatorUnclear:
    """Tests for transcripts that should fail validation."""

    def test_empty_text(self):
        t = Transcript(text="", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear
        assert result.status == ValidationStatus.UNCLEAR
        assert "empty" in result.reason.lower()

    def test_whitespace_only(self):
        t = Transcript(text="   \n\t  ", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear

    def test_too_short(self):
        t = Transcript(text="H", confidence=0.9)
        result = validate(t, config=_make_config(validator_min_length=2))
        assert not result.is_clear
        assert "short" in result.reason.lower()

    def test_low_confidence(self):
        t = Transcript(text="Hello world", confidence=0.2)
        result = validate(t, config=_make_config(validator_min_confidence=0.4))
        assert not result.is_clear
        assert "confidence" in result.reason.lower()

    def test_hallucination_thank_you(self):
        t = Transcript(text="Thank you for watching.", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear
        assert "hallucination" in result.reason.lower()

    def test_hallucination_subscribe(self):
        t = Transcript(text="Please subscribe.", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear

    def test_hallucination_music_bracket(self):
        t = Transcript(text="[Music]", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear

    def test_hallucination_repeated_chars(self):
        t = Transcript(text="aaaaa", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear

    def test_hallucination_dots(self):
        t = Transcript(text="...", confidence=0.9)
        result = validate(t, config=_make_config())
        assert not result.is_clear
