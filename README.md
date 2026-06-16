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

> **This is the core extension point of this repo.** Everything below is a
> deliberate STUB / TODO. The free-text `personality.system_prompt`, `greeting`,
> and KB content can be authored in Urdu immediately — only the speech engines
> and a few framework prompt fragments need code.

Edit exactly these files/functions (each is marked with `TODO(urdu)` in code):

- [ ] **STT engine** — implement `src/pipeline/providers/urdu_stt.py`
      (`UrduSTT`). Model it on `custom_stt.py` (HTTP/batch) or `navai_ws_stt.py`
      (streaming + barge-in). Reads `URDU_STT_URL`.
- [ ] **TTS engine** — implement `src/pipeline/providers/urdu_tts.py`
      (`UrduTTS`). Model it on `custom_tts.py` (HTTP/batch) or `navai_ws_tts.py`
      (streaming `ChunkedStream`). Reads `URDU_TTS_URL` / `URDU_VOICE_ID`.
- [x] **Factory dispatch** — `src/pipeline/voice_factory.py` already has
      `elif provider == "urdu_stt"` / `"urdu_tts"` branches wired to the stubs.
- [x] **Locale map** — `_LANG_MAP` in `voice_factory.py` already maps
      `"ur" → "ur-PK"` (required, or `ur` silently falls back to `uz-UZ`).
- [ ] **Tenant config** — set `voice.stt_provider: urdu_stt`,
      `voice.tts_provider: urdu_tts`, `voice.voices: {ur: <voice>}`, and
      `languages: {default: ur, available: [ur]}` in the tenant YAML.
- [ ] **Localized prompt fragments** — `src/agents/factory.py`
      (`_build_instructions`, `_csat_policy_instructions`,
      `_response_format_instructions`) have hard-coded Uzbek/Russian policy text
      with `TODO(urdu)` markers and `ur` stub branches that currently fall back
      to the default. Add Urdu text there for natural framework prompts.
- [ ] **`get_current_time` tool** — `src/tools/platform/get_time.py` returns an
      Uzbek-formatted sentence (TZ is already config-driven, default
      `Asia/Karachi`). Add Urdu phrasing when wiring an Urdu tenant.
- [x] **Timezone** — out-of-hours check is config-driven
      (`transfer.timezone`, default `Asia/Karachi`) in
      `src/tools/platform/escalate.py`.
- [ ] **`.env`** — set `URDU_STT_URL`, `URDU_TTS_URL`, `URDU_VOICE_ID`.

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
