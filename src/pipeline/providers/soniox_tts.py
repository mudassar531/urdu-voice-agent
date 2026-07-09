"""
Urdu TTS (Text-to-Speech) provider — Soniox real-time streaming backend.

Thin wrapper around ``livekit.plugins.soniox.TTS`` so the ``soniox`` factory
branch (``src/pipeline/voice_factory.py``) keeps a stable class shape while we
delegate synthesis to Soniox's streaming WebSocket TTS API. Soniox provides
high-fidelity Urdu speech with native-speaker fluency and streaming output
(audio starts before the full sentence is ready), which keeps voice-agent
latency low.

Using Soniox for both STT and TTS means the whole speech layer runs on a single
``SONIOX_API_KEY``. Auth comes from that env var (read by the plugin, or passed
explicitly here) — see ``.env.example``. Per-tenant voice selection flows
through ``voice.tts_voice_id`` / ``voice.voices`` in the YAML.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from livekit.plugins.soniox import TTS as _SonioxTTS

from observability.network_topology import register_service_route

logger = logging.getLogger(__name__)

_SONIOX_TTS_URL = "wss://tts-rt.soniox.com/tts-websocket"
_DEFAULT_MODEL = "tts-rt-v1-preview"
# Soniox's multilingual voices speak whichever `language` they're given; "Maya"
# is the platform default. Operators override per-tenant via voice.tts_voice_id.
_DEFAULT_VOICE = "Maya"


def _resolve_language(language: str | None) -> str:
    """Normalize an incoming locale (e.g. ``ur-PK``) to a Soniox code (``ur``)."""
    return (language or "ur").split("-")[0].lower()


def _resolve_voice(voice: str | None) -> str:
    if voice:
        return voice
    return os.getenv("SONIOX_TTS_VOICE") or _DEFAULT_VOICE


class SonioxTTS(_SonioxTTS):
    """Urdu TTS backed by Soniox streaming synthesis."""

    def __init__(
        self,
        *,
        voice: str | None = None,
        language: str = "ur-PK",
        sample_rate: int = 24000,
        speed: float = 1.0,
        api_key: str | None = None,
        model: str | None = None,
        **_unused: Any,
    ) -> None:
        resolved_key = api_key or os.getenv("SONIOX_API_KEY")
        if not resolved_key:
            raise RuntimeError("Soniox TTS requires SONIOX_API_KEY — set it in your .env.")

        lang = _resolve_language(language)
        resolved_voice = _resolve_voice(voice)
        resolved_model = model or os.getenv("SONIOX_TTS_MODEL", _DEFAULT_MODEL)

        super().__init__(
            api_key=resolved_key,
            model=resolved_model,
            language=lang,
            voice=resolved_voice,
            sample_rate=sample_rate,
        )

        # Telephony timing callback (set by main.py); kept for parity. Soniox
        # TTS has no server-side speed control, so `speed` is retained only so
        # the factory can pass it uniformly across providers.
        self._on_tts_duration = None
        self._language_label = language
        self._speed = speed

        register_service_route(
            "soniox_tts",
            _SONIOX_TTS_URL,
            provider="soniox",
            metadata={"voice": resolved_voice, "language": lang, "model": resolved_model},
        )
        logger.info(
            "SonioxTTS initialized: voice=%s, language=%s, model=%s, sample_rate=%d",
            resolved_voice,
            lang,
            resolved_model,
            sample_rate,
        )
