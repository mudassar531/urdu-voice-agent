# urdu-voice-agent

A multi-tenant, real-time **voice AI agent** building block, built on the
[LiveKit Agents](https://docs.livekit.io/agents/) SDK. A single Python binary
serves N tenants; each tenant's behavior is defined entirely by a YAML config +
a per-tenant knowledge base. The LLM is the conversation controller (KB search,
flows, escalation, tool calls).

This repo is a **blueprint / scaffolding**: the architecture is faithful and
runnable (minus secrets and self-hosted engines), with clearly-marked **Urdu
integration seams** (STUBs) where you plug in an Urdu STT/TTS engine. It does
**not** ship a real Urdu speech engine — see ["Urdu integration seams"](#urdu-integration-seams).

> Architecture deep-dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## The realtime pipeline

Per call, LiveKit's `AgentSession` runs a cascading pipeline:

```
mic audio → VAD (endpointing) → STT → LLM (with tools) → TTS → room playback
            (Silero)            (per-tenant provider)     (Gemini/…)  (per-tenant provider)
```

- **Entry point:** `src/main.py` — a LiveKit `AgentServer` worker (port `8088`)
  with a separate health/observability HTTP server (port `8082`). One per-call
  entrypoint is registered via `@server.rtc_session(agent_name=AGENT_NAME)`.
- **Per call:** classify → extract the **called** phone → resolve tenant →
  fetch caller history → pick effective language → build STT/TTS/LLM → warm KB →
  build agent → create call record → start `AgentSession` → connect.
- **Provider dispatch lives in ONE file:** `src/pipeline/voice_factory.py`
  (`create_stt_for_language`, `create_tts_for_language`, `create_llm`), keyed by
  string provider names from the tenant YAML. This is the Urdu swap point.

Default stack (out of the box): **managed LiveKit inference gateway** for STT
(deepgram) and TTS (cartesia) + **Gemini** (Vertex ADC) for the LLM + Silero
VAD. No self-hosted engine is required to run the example tenant locally.

---

## Multi-tenant model

- A tenant = one `configs/tenants/<slug>.yaml`, validated by the Pydantic
  `TenantConfig` (`src/config/schema.py`).
- The loader **deep-merges** `_defaults.yaml ← <slug>.yaml`, then applies
  per-environment id/phone overrides from `configs/environments.yaml`
  (selected by `CONFIG_ENV`), then validates.
- **Routing is by the CALLED (destination) phone number**, never by agent name
  or room name (`src/config/routing.py`). `MULTI_TENANT_STRICT_ROUTING=true`
  fails closed on unknown numbers.
- Per-tenant Platform API keys are resolved **data-driven** from the env var
  `{SLUG_UPPER}_AGENT_API_KEY` (slug uppercased, non-alphanumerics → `_`), e.g.
  `example-tenant` → `EXAMPLE_TENANT_AGENT_API_KEY` (`src/config/api_keys.py`).
  Onboarding a tenant is a config/env change, not a code edit.
- A/B experiments: variant YAMLs sharing `experiment.id` are weighted-random
  picked per call.

---

## Run locally

Prereqs: [`uv`](https://github.com/astral-ftw/uv), Docker, and (for Gemini)
`gcloud auth application-default login`.

```bash
# 1. Install deps into a local venv
uv venv && uv pip install -e ".[dev]"

# 2. Configure env
cp .env.example .env        # fill in LIVEKIT_* and PLATFORM_API_URL at minimum

# 3. Start Qdrant (+ agent) via compose, or just Qdrant for local dev
docker compose up qdrant -d
# OR the full stack (agent + monitor + qdrant):
# docker compose up --build

# 4. Populate the example tenant's KB into Qdrant
PYTHONPATH=src python scripts/populate_qdrant.py \
    --source knowledge/example-tenant/faq_source.json \
    --collection example_tenant_faq

# 5. Run the agent worker (PYTHONPATH=src is required — flat imports)
PYTHONPATH=src python src/main.py start

# Local dev without the real Platform API: a mock backend stands in for the
# agent-ingestion endpoints. Point PLATFORM_API_URL at it.
python scripts/mock_backend.py          # port 3000
```

Two ports to keep straight: the LiveKit worker listens on **8088**; the
observability/health server (`/health`, `/network/topology`) listens on
**8082** (the Dockerfile `EXPOSE`).

### Tests, lint, eval

```bash
pytest tests/unit -v
pytest tests/integration -v
ruff check src tests scripts --fix
black src tests scripts
python eval/run_eval.py                  # scenario eval (configs/tenants/example-tenant.yaml)
python eval/check_kb.py --ssh --host user@<your-server>   # KB retrieval health
```

---

## Onboarding a tenant

1. Copy the documented skeleton:
   `cp configs/tenants/_template.yaml configs/tenants/<slug>.yaml` and fill in
   `tenant.id` (Mongo ObjectId from the platform), `slug`, `name`,
   `phone_numbers: ["+92…"]`, `personality.*`, `voice.*`, `languages.*`,
   `knowledge_base.collection: <slug>_faq`, `transfer.*` (incl. `timezone`).
2. Add `prod` + `dev` entries (id + phone) to `configs/environments.yaml`.
3. Author `knowledge/<kb-dir>/faq_source.json` (schema in
   [`knowledge/README.md`](knowledge/README.md)) and populate Qdrant.
4. Provision the per-tenant API key: set `{SLUG_UPPER}_AGENT_API_KEY` in the env.
5. Provision telephony + the platform tenant record (separate infra/platform
   repos). The same DID must agree across Asterisk, LiveKit dispatch, the tenant
   YAML, and the platform record.

Full runbook: `BLUEPRINT-PLAN.md` §4 (in the research bundle).

---

## Urdu integration seams

> **The Urdu STT and TTS seams are now wired to real engines** —
> Speechmatics (real-time streaming Urdu STT) and Azure Cognitive Services
> (neural Urdu voices). Free-text `personality.system_prompt`, `greeting`,
> and KB content can be authored directly in Urdu / Roman-Urdu.

Status of each seam:

- [x] **STT engine** — `src/pipeline/providers/urdu_stt.py` (`UrduSTT`)
      subclasses `livekit.plugins.speechmatics.STT`. Reads
      `SPEECHMATICS_API_KEY` (and optionally `URDU_STT_URL` to override the
      default `wss://eu2.rt.speechmatics.com/v2`).
- [x] **TTS engine** — `src/pipeline/providers/urdu_tts.py` (`UrduTTS`)
      subclasses `livekit.plugins.azure.TTS`. Reads `AZURE_SPEECH_KEY` plus
      either `AZURE_SPEECH_REGION` or `AZURE_SPEECH_ENDPOINT`. Default voice
      is `ur-PK-UzmaNeural`; override via `voice.tts_voice_id` /
      `voice.voices` in the YAML or `URDU_VOICE_ID` env.
- [x] **Factory dispatch** — `src/pipeline/voice_factory.py` routes
      `voice.stt_provider: urdu_stt` and `voice.tts_provider: urdu_tts` to
      the implementations above. The `gemini_api` LLM provider lets the
      agent run with a Google AI Studio key (no Vertex ADC required).
- [x] **Locale map** — `_LANG_MAP` in `voice_factory.py` maps
      `"ur" → "ur-PK"`.
- [x] **Tenant config** — see `configs/tenants/hashim-girls-hostel.yaml`
      for a working Urdu single-language tenant.
- [ ] **Localized prompt fragments** — `src/agents/factory.py`
      (`_build_instructions`, `_csat_policy_instructions`,
      `_response_format_instructions`) still have hard-coded Uzbek/Russian
      policy text with `TODO(urdu)` markers. Add Urdu phrasing there for
      maximum naturalness.
- [ ] **`get_current_time` tool** — `src/tools/platform/get_time.py`
      returns an Uzbek-formatted sentence (TZ defaults to `Asia/Karachi`).
      Add Urdu phrasing when polish is needed.
- [x] **Timezone** — `transfer.timezone` defaults to `Asia/Karachi`.
- [x] **`.env`** — set `SPEECHMATICS_API_KEY`, `AZURE_SPEECH_KEY`,
      `AZURE_SPEECH_REGION` (or `AZURE_SPEECH_ENDPOINT`), and
      `GOOGLE_API_KEY` for the `gemini_api` LLM path.

See `BLUEPRINT-PLAN.md` §3 for the full seam spec.

---

## Layout

```
src/
  main.py                     worker bootstrap + per-call entrypoint
  config/                     TenantConfig schema, loader, registry, routing, api_keys
  pipeline/                   voice_factory (provider dispatch), session_builder, providers/
  agents/                     TenantAgent, AgentFactory, sub_agents/
  tools/                      tool registry + platform/ + tenant/ tools
  flows/                      .flow.md engine
  knowledge/                  RAG engine, KB manager, deterministic point ids
  lifecycle/ observability/ resilience/ api/   call lifecycle, metrics, silence monitor, platform client
configs/tenants/              _defaults.yaml, _template.yaml, example-tenant.yaml
knowledge/<kb-dir>/           faq_source.json (+ optional flows/)
eval/                         run_eval.py (scenarios) + check_kb.py
scripts/                      populate_qdrant.py, agent_monitor.py, mock_backend.py, ws clients
```
