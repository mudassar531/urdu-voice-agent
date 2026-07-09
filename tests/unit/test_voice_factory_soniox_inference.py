"""Tests for the Soniox STT/TTS and LiveKit Inference (Gemma) factory branches."""

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
    cls_mock = MagicMock()
    mod_mock = ModuleType(class_name)
    setattr(mod_mock, class_name, cls_mock)
    return mod_mock, cls_mock


def test_create_stt_soniox_passes_urdu_locale():
    mod, cls_mock = _make_provider_mock("SonioxSTT")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_stt": mod}):
        config = _base_config(stt_provider="soniox")
        VoiceFactory.create_stt_for_language(config, "ur")
    cls_mock.assert_called_once()
    assert cls_mock.call_args.kwargs["language"] == "ur-PK"


def test_create_tts_soniox_passes_voice_and_locale():
    mod, cls_mock = _make_provider_mock("SonioxTTS")
    with patch.dict(sys.modules, {"pipeline.providers.soniox_tts": mod}):
        config = _base_config(
            tts_provider="soniox",
            tts_voice_id="Maya",
            voices={"ur": "Maya"},
        )
        VoiceFactory.create_tts_for_language(config, "ur")
    cls_mock.assert_called_once()
    assert cls_mock.call_args.kwargs["voice"] == "Maya"
    assert cls_mock.call_args.kwargs["language"] == "ur-PK"


def test_create_llm_inference_uses_model_string():
    with patch("livekit.agents.inference.LLM") as llm_cls:
        config = _base_config()
        config.llm.provider = "inference"
        config.llm.model = "google/gemma-4-31b-it"
        config.llm.temperature = 0.2
        VoiceFactory.create_llm(config)
    llm_cls.assert_called_once()
    assert llm_cls.call_args.kwargs["model"] == "google/gemma-4-31b-it"
    # temperature is passed through extra_kwargs (inference.LLM has no temp arg)
    assert llm_cls.call_args.kwargs["extra_kwargs"]["temperature"] == 0.2


def test_create_llm_inference_defaults_to_gemma():
    with patch("livekit.agents.inference.LLM") as llm_cls:
        config = _base_config()
        config.llm.provider = "gemma"  # alias for the inference branch
        config.llm.model = ""
        VoiceFactory.create_llm(config)
    assert llm_cls.call_args.kwargs["model"] == "google/gemma-4-31b-it"
