import pytest
from pydantic import ValidationError

from app.config import Settings


def test_native_voice_defaults_to_gemini_31_only():
    settings = Settings(_env_file=None)
    assert settings.gemini_live_model == "gemini-3.1-flash-live-preview"
    assert settings.gemini_live_thinking_level == "low"


def test_alternate_voice_model_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_live_model="gemini-2.5-flash-native-audio-preview-12-2025")


@pytest.mark.parametrize("level", ["minimal", "low", "medium", "high"])
def test_native_thinking_level_is_configurable_from_environment(monkeypatch, level):
    monkeypatch.setenv("JANMITRA_GEMINI_LIVE_THINKING_LEVEL", level)
    assert Settings(_env_file=None).gemini_live_thinking_level == level


@pytest.mark.parametrize("level", ["", "automatic", "off", "LOW", "0"])
def test_unsupported_native_thinking_level_is_rejected(level):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_live_thinking_level=level)
