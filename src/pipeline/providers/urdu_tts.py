"""
Urdu TTS (Text-to-Speech) provider — STUB / integration seam.

>>> TODO(urdu): IMPLEMENT THIS. This is a blueprint stub, NOT a working engine.

This class is the Urdu TTS integration seam referenced by
`VoiceFactory.create_tts_for_language` (branch `provider == "urdu_tts"`) and by
the README "Urdu integration seams" section. It imports cleanly so the repo
loads, but `synthesize()` raises NotImplementedError until you wire a real engine.

HOW TO IMPLEMENT
----------------
Copy the shape of an existing, working provider and adapt it to your Urdu engine:

  * HTTP / batch GPU server  -> copy `src/pipeline/providers/custom_tts.py`
      (`CustomTTS` + `CustomTTSStream`): `TTSCapabilities(streaming=False)`,
      implement `synthesize(text, ...)` returning a stream object that yields
      one `tts.SynthesizedAudio` per chunk. POST the text to your server, parse
      the returned WAV, convert to an `rtc.AudioFrame`. Simplest starting point.

  * WebSocket / streaming      -> copy `src/pipeline/providers/navai_ws_tts.py`
      (`NavaiWSTTS`): the livekit 1.5.x `tts.ChunkedStream` API
      (`ChunkedStream._run` -> `output_emitter.push(bytes)`). Streams frames as
      they arrive (lower TTFB). IMPORTANT invariant: do NOT retry after the
      first audio frame has been emitted, or the caller hears doubled speech.

REQUIREMENTS (from doc 01 §4e)
------------------------------
  * Subclass `livekit.agents.tts.TTS`; pass `sample_rate` / `num_channels` and
    `TTSCapabilities` to `super().__init__`.
  * Audio prep: emit PCM16 mono resampled to your declared `sample_rate`
    (see custom_tts.py `_wav_to_audio_frame`).
  * Read endpoint + voice from env: `URDU_TTS_URL`, `URDU_VOICE_ID`
    (add both to `.env.example`).
  * Conventionally call `register_service_route(...)` and expose the
    `_on_tts_duration` callback for telemetry.

CONFIG WIRING
-------------
  voice.tts_provider: urdu_tts
  voice.tts_voice_id: <urdu_voice>      # or voice.voices: {ur: <urdu_voice>}
  # .env: URDU_TTS_URL=...  URDU_VOICE_ID=...
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from livekit.agents import tts

from observability.network_topology import register_service_route

logger = logging.getLogger(__name__)

_NOT_IMPLEMENTED_MSG = (
    "TODO(urdu): implement Urdu TTS — see README 'Urdu integration seams' "
    "and the docstring in src/pipeline/providers/urdu_tts.py (model on "
    "custom_tts.py for HTTP/batch or navai_ws_tts.py for streaming)."
)


class UrduTTS(tts.TTS):
    """STUB Urdu TTS provider. Raises NotImplementedError until wired."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        voice: str | None = None,
        language: str = "ur-PK",
        sample_rate: int = 24000,
        num_channels: int = 1,
        speed: float = 1.0,
    ) -> None:
        # Default to a non-streaming shape (simplest). Switch to streaming=True
        # when modeling on navai_ws_tts.py / ChunkedStream.
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )
        self._base_url = (base_url or os.getenv("URDU_TTS_URL", "")).rstrip("/")
        self._voice = voice or os.getenv("URDU_VOICE_ID", "")
        self._language = language
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._speed = speed

        # Telephony timing callback (set by main.py); kept for parity.
        self._on_tts_duration = None

        if self._base_url:
            register_service_route(
                "urdu_tts",
                self._base_url,
                provider="urdu_tts",
                metadata={"voice": self._voice, "speed": self._speed},
            )
        logger.warning(
            "UrduTTS is a STUB (url=%r, voice=%r, lang=%s). %s",
            self._base_url or "<unset URDU_TTS_URL>",
            self._voice or "<unset URDU_VOICE_ID>",
            self._language,
            _NOT_IMPLEMENTED_MSG,
        )

    def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        conn_options: Optional[dict] = None,
    ):
        """TODO(urdu): synthesize `text` and return a stream of SynthesizedAudio.

        Reference implementation: custom_tts.py `synthesize` + `CustomTTSStream`
        (HTTP batch) or navai_ws_tts.py (streaming ChunkedStream).
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
