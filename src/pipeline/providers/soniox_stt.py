"""
Urdu STT (Speech-to-Text) provider — Soniox real-time streaming backend.

Thin wrapper around ``livekit.plugins.soniox.STT`` so the ``soniox`` factory
branch (``src/pipeline/voice_factory.py``) keeps a stable class shape while we
delegate the heavy lifting to Soniox's streaming WebSocket STT API. Soniox
natively supports Urdu (``ur``) with real-time partials and automatic language
identification, so no extra locale mapping is needed beyond stripping the
``-PK`` suffix.

Auth comes from ``SONIOX_API_KEY`` (read by the plugin itself, or passed
explicitly here) — see ``.env.example``. Soniox streams interim transcripts,
which the agent uses for barge-in.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from livekit.plugins.soniox import STT as _SonioxSTT
from livekit.plugins.soniox import STTOptions

from observability.network_topology import register_service_route

logger = logging.getLogger(__name__)

_SONIOX_STT_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
_DEFAULT_MODEL = "stt-rt-v5"


def _resolve_language_hints(language: str | None) -> list[str]:
    """Normalize an incoming locale (e.g. ``ur-PK``) into Soniox language hints.

    Urdu callers routinely code-switch into English (numbers, names, brand
    words), so we hint both the primary language and English. Soniox's language
    identification (enabled below) then transcribes each word in whichever of
    the hinted languages it hears, rather than locking onto one script.
    """
    base = (language or "ur").split("-")[0].lower()
    hints = [base]
    if base != "en":
        hints.append("en")
    return hints


class SonioxSTT(_SonioxSTT):
    """Urdu STT backed by Soniox real-time transcription."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        language: str = "ur-PK",
        sample_rate: int = 16000,
        model: str | None = None,
        vad: Any = None,
        **_unused: Any,
    ) -> None:
        resolved_key = api_key or os.getenv("SONIOX_API_KEY")
        if not resolved_key:
            raise RuntimeError("Soniox STT requires SONIOX_API_KEY — set it in your .env.")

        hints = _resolve_language_hints(language)
        resolved_model = model or os.getenv("SONIOX_STT_MODEL", _DEFAULT_MODEL)
        params = STTOptions(
            model=resolved_model,
            language_hints=hints,
            sample_rate=sample_rate,
            enable_language_identification=True,
        )

        super().__init__(api_key=resolved_key, params=params)

        # Telephony timing callbacks (set by main.py); kept for parity with the
        # other providers — Soniox already streams partials so we rely on the
        # session's tracker hooks for latency reporting.
        self._first_audio_signaled = False
        self._on_first_audio = None
        self._on_stt_duration = None
        self._vad = vad
        self._language_label = language

        register_service_route(
            "soniox_stt",
            _SONIOX_STT_URL,
            provider="soniox",
            metadata={"language_hints": hints, "model": resolved_model, "session_locale": language},
        )
        logger.info(
            "SonioxSTT initialized: hints=%s, model=%s, sample_rate=%d",
            hints,
            resolved_model,
            sample_rate,
        )
