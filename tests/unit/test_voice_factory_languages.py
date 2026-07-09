"""Tests for per-language STT/TTS helpers on VoiceFactory."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from config.schema import TenantConfig, TenantIdentity, VoiceConfig
from pipeline.voice_factory import VoiceFactory


def _base_config(**voice_kwargs):
    return TenantConfig(
        tenant=TenantIdentity(id="t1"),
        voice=VoiceConfig(**voice_kwargs),
    )


def _make_provider_mock(class_name: str) -> tuple[ModuleType, MagicMock]:
    """Return a (module_mock, class_mock) pair for a provider module."""
    cls_mock = MagicMock()
    mod_mock = ModuleType(class_name)
    setattr(mod_mock, class_name, cls_mock)
    return mod_mock, cls_mock


def test_create_stt_for_language_passes_correct_locale():
    mod, cls_mock = _make_provider_mock("SonioxSTT")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_stt": mod}):
        config = _base_config(stt_provider="soniox")
        VoiceFactory.create_stt_for_language(config, "ru")
    cls_mock.assert_called_once()
    assert cls_mock.call_args.kwargs["language"] == "ru-RU"


def test_create_stt_for_language_uses_stt_providers_mapping():
    soniox_mod, soniox_cls = _make_provider_mock("SonioxSTT")
    custom_mod, custom_cls = _make_provider_mock("CustomSTT")
    with patch.dict(
        sys.modules,
        {
            "pipeline.providers.soniox_stt": soniox_mod,
            "pipeline.providers.custom_stt": custom_mod,
        },
    ):
        config = _base_config(
            stt_provider="custom",
            stt_providers={"ru": "soniox", "en": "custom"},
        )
        VoiceFactory.create_stt_for_language(config, "ru")
        VoiceFactory.create_stt_for_language(config, "en")
    assert soniox_cls.call_count == 1
    assert soniox_cls.call_args.kwargs["language"] == "ru-RU"
    assert custom_cls.call_count == 1
    assert custom_cls.call_args.kwargs["language"] == "en"


def test_create_tts_for_language_uses_voices_mapping():
    mod, cls_mock = _make_provider_mock("SonioxTTS")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_tts": mod}):
        config = _base_config(
            tts_provider="soniox",
            voices={"ru": "voice_ru", "en": "voice_en"},
        )
        VoiceFactory.create_tts_for_language(config, "ru")
    cls_mock.assert_called_once()
    assert cls_mock.call_args.kwargs["voice"] == "voice_ru"
    assert cls_mock.call_args.kwargs["language"] == "ru-RU"


def test_create_tts_for_language_falls_back_to_tts_voice_id():
    mod, cls_mock = _make_provider_mock("SonioxTTS")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_tts": mod}):
        config = _base_config(
            tts_provider="soniox",
            tts_voice_id="default_voice",
            voices={},
        )
        VoiceFactory.create_tts_for_language(config, "en")
    assert cls_mock.call_args.kwargs["voice"] == "default_voice"


def test_create_stt_delegates_to_language_helper():
    """Backward compat: create_stt uses behavior.language."""
    mod, cls_mock = _make_provider_mock("SonioxSTT")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_stt": mod}):
        config = TenantConfig(
            tenant=TenantIdentity(id="t1"),
            voice=VoiceConfig(stt_provider="soniox"),
        )
        config.behavior.language = "ru"
        VoiceFactory.create_stt(config)
        assert cls_mock.call_args.kwargs["language"] == "ru-RU"


def test_create_stt_for_language_unknown_code_falls_back_to_urdu_locale():
    mod, cls_mock = _make_provider_mock("SonioxSTT")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_stt": mod}):
        config = _base_config(stt_provider="soniox")
        VoiceFactory.create_stt_for_language(config, "xx")
    assert cls_mock.call_args.kwargs["language"] == "ur-PK"
