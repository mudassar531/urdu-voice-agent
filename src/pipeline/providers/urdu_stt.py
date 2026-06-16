"""
Urdu STT (Speech-to-Text) provider — STUB / integration seam.

>>> TODO(urdu): IMPLEMENT THIS. This is a blueprint stub, NOT a working engine.

This class is the Urdu STT integration seam referenced by
`VoiceFactory.create_stt_for_language` (branch `provider == "urdu_stt"`) and by
the README "Urdu integration seams" section. It imports cleanly so the repo
loads, but every method raises NotImplementedError until you wire a real engine.

HOW TO IMPLEMENT
----------------
Copy the shape of an existing, working provider and adapt it to your Urdu engine:

  * HTTP / batch GPU server  -> copy `src/pipeline/providers/custom_stt.py`
      (`CustomSTT`): `STTCapabilities(streaming=False, interim_results=False)`,
      implement `async def _recognize_impl(self, buffer, *, language=None,
      conn_options=None) -> stt.SpeechEvent`. POST WAV bytes to your server,
      parse the transcript, return a FINAL_TRANSCRIPT SpeechEvent. This is the
      simplest starting point and matches a GPU batch STT server.

  * WebSocket / streaming      -> copy `src/pipeline/providers/navai_ws_stt.py`
      (`NavaiWSSTT`): `STTCapabilities(streaming=True, interim_results=True)`,
      implement `stream()` returning a RecognizeStream that does its OWN VAD
      endpointing (uses the injected Silero `vad`). Required for barge-in /
      interim transcripts.

REQUIREMENTS (from doc 01 §4e)
------------------------------
  * Subclass `livekit.agents.stt.STT` and set capabilities in `super().__init__`.
  * Audio prep: convert input to PCM16 mono and resample to your server's rate
    (see the `np.interp` resample pattern in custom_stt.py `_prepare_wav`).
  * Read your endpoint from env: `URDU_STT_URL` (add it to `.env.example`).
  * Conventionally call `register_service_route(...)` for the topology view and
    expose `_on_first_audio` / `_on_stt_duration` callbacks for telemetry.

CONFIG WIRING
-------------
  voice.stt_provider: urdu_stt          # or voice.stt_providers: {ur: urdu_stt}
  languages: {default: ur, available: [ur]}
  # .env: URDU_STT_URL=...
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union

from livekit import rtc
from livekit.agents import stt

from observability.network_topology import register_service_route

logger = logging.getLogger(__name__)

_NOT_IMPLEMENTED_MSG = (
    "TODO(urdu): implement Urdu STT — see README 'Urdu integration seams' "
    "and the docstring in src/pipeline/providers/urdu_stt.py (model on "
    "custom_stt.py for HTTP/batch or navai_ws_stt.py for streaming)."
)


class UrduSTT(stt.STT):
    """STUB Urdu STT provider. Raises NotImplementedError until wired."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        language: str = "ur-PK",
        sample_rate: int = 16000,
        vad: Any = None,
    ) -> None:
        # Default to a non-streaming batch shape (simplest). Switch to
        # streaming=True / interim_results=True when modeling on navai_ws_stt.py.
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )
        self._base_url = (base_url or os.getenv("URDU_STT_URL", "")).rstrip("/")
        self._language = language
        self._sample_rate = sample_rate
        self._vad = vad

        # Telephony timing callbacks (set by main.py). Kept for parity with the
        # other providers so a real implementation can fire them.
        self._first_audio_signaled = False
        self._on_first_audio = None
        self._on_stt_duration = None

        if self._base_url:
            register_service_route(
                "urdu_stt",
                self._base_url,
                provider="urdu_stt",
                metadata={"language": self._language},
            )
        logger.warning(
            "UrduSTT is a STUB (url=%r, lang=%s). %s",
            self._base_url or "<unset URDU_STT_URL>",
            self._language,
            _NOT_IMPLEMENTED_MSG,
        )

    async def _recognize_impl(
        self,
        buffer: Union[rtc.AudioFrame, bytes],
        *,
        language: Optional[str] = None,
        conn_options: Optional[dict] = None,
    ) -> stt.SpeechEvent:
        """TODO(urdu): transcribe `buffer` and return a SpeechEvent.

        Reference implementation: custom_stt.py `_recognize_impl` (HTTP batch).
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
