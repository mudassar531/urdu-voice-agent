"""
Urdu STT (Speech-to-Text) provider — Azure Cognitive Services backend.

Thin wrapper around `livekit.plugins.azure.STT`. Exists specifically so a
tenant can use Azure for BOTH STT and TTS (see urdu_tts.py) and pay the
`livekit-plugins-azure` import cost exactly once, instead of stacking it on
top of `livekit-plugins-speechmatics` (see urdu_stt.py) -- the latter
combination was confirmed (via memory-checkpoint instrumentation) to OOM a
512MB Render instance on the Speechmatics import alone, before Azure was
ever reached. Untested whether Azure-only fits; this is that experiment.

Azure STT's confirmed Urdu locale is `ur-IN` (Urdu, India) -- there is no
`ur-PK` STT locale as of this writing (unlike Azure's TTS voices, which do
ship `ur-PK-*`). `ur-IN` and Pakistani Urdu are close enough dialects that
this should transcribe reasonably; override via AZURE_STT_LANGUAGE if Azure
adds a PK locale later.

Auth comes from `AZURE_SPEECH_KEY` plus `AZURE_SPEECH_REGION` (or
`AZURE_SPEECH_ENDPOINT`), same as urdu_tts.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from livekit.plugins.azure import STT as AzureSTT

from observability.network_topology import register_service_route

logger = logging.getLogger(__name__)

_DEFAULT_AZURE_STT_LANGUAGE = "ur-IN"


def _resolve_speech_key() -> str | None:
    return os.getenv("AZURE_SPEECH_KEY") or os.getenv("URDU_STT_API_KEY")


def _resolve_speech_region() -> str | None:
    return os.getenv("AZURE_SPEECH_REGION")


def _resolve_speech_endpoint() -> str | None:
    """Same convention as urdu_tts.py: only honor an explicit synthesis-shaped
    URL, since the Azure portal's resource endpoint is NOT the STT endpoint."""
    explicit = os.getenv("AZURE_SPEECH_ENDPOINT", "").strip()
    if explicit and "cognitiveservices" in explicit:
        return explicit
    return None


class AzureUrduSTT(AzureSTT):
    """Urdu STT backed by Azure Cognitive Services."""

    def __init__(
        self,
        *,
        language: str = _DEFAULT_AZURE_STT_LANGUAGE,
        sample_rate: int = 16000,
        vad: Any = None,
        **_unused: Any,
    ) -> None:
        speech_key = _resolve_speech_key()
        speech_region = _resolve_speech_region()
        speech_endpoint = _resolve_speech_endpoint()

        if not speech_key and not speech_endpoint:
            raise RuntimeError(
                "Azure Urdu STT requires AZURE_SPEECH_KEY plus AZURE_SPEECH_REGION "
                "(or a synthesis AZURE_SPEECH_ENDPOINT containing 'cognitiveservices') "
                "— set them in your .env."
            )

        stt_language = os.getenv("AZURE_STT_LANGUAGE", "").strip() or _DEFAULT_AZURE_STT_LANGUAGE

        super().__init__(
            speech_key=speech_key,
            speech_region=speech_region,
            speech_endpoint=speech_endpoint,
            language=stt_language,
            sample_rate=sample_rate,
        )

        self._on_stt_duration = None
        self._vad = vad
        self._language_label = language

        topology_target = speech_endpoint or (
            f"https://{speech_region}.stt.speech.microsoft.com" if speech_region else "azure-stt"
        )
        register_service_route(
            "azure_stt",
            topology_target,
            provider="azure_speech",
            metadata={"language": stt_language, "session_locale": language},
        )
        logger.info(
            "AzureUrduSTT initialized: endpoint=%s, language=%s, sample_rate=%d",
            topology_target,
            stt_language,
            sample_rate,
        )
