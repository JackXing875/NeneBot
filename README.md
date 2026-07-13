# Persona Studio

> NeneBot 0.7 migration preview — a local-first, auditable Character Agent Studio and
> Runtime.

[中文说明](README_ch.md) · [Migration roadmap](MEMORY.md) ·
[Character Pack v1](docs/character-packs.md)

This repository is being rebuilt from a single-character RAG demo into a general platform for
authoring, validating, testing, and running character agents. The migration is incremental: the
0.7 branch still runs the compatibility application while new content and runtime boundaries are
introduced alongside it.

## What exists today

The following describes the current 0.7 compatibility runtime, not the finished Studio:

- a FastAPI backend with the legacy `POST /v1/chat` and `POST /v1/chat/stream` APIs;
- incremental SSE output, request limits, scoped token authentication, and operational probes;
- a Vue/Vite chat client and an operations-oriented admin page;
- Ollama, Anthropic, and OpenAI-compatible LLM adapters;
- the legacy FAISS/sentence-transformers retrieval pipeline;
- process-local session history by default, with Redis as an optional backend;
- strict Character Pack JSON v1 validation and immutable Artifact staging/publishing helpers.

Character Packs and versioned Artifacts are a foundation at this stage. They are not yet the
default content source for `/v1/chat`, and the current front end is not yet a complete pack editor.
The legacy RAG routes remain available as a compatibility surface while that integration is built.

Legacy online knowledge import and index rebuild endpoints are disabled by default. Knowledge
should be validated and built offline, then published as an immutable Artifact. See
[Character Pack and Artifact v1](docs/character-packs.md) for the implemented schema, provenance
rules, integrity checks, atomic publish model, and current limitations.

## Where the project is going

The target product is a modular, local-first Persona Studio built around one versioned Character
Pack boundary:

- persona, prompt, examples, knowledge, theme, evaluation fixtures, source, licence, and safety
  metadata travel together;
- an offline builder validates content and publishes a traceable, rollback-safe Artifact;
- one Agent Kernel serves the web compatibility API and explicitly authorised transports;
- typed events and policy-checked actions make agent behaviour replayable and auditable;
- a Studio supports pack review, evaluation, publish, and rollback;
- an offline group-chat simulator evaluates decisions before any real message can be sent;
- privacy controls precede durable memory or autonomous external integrations.

These items are staged goals, not claims about the current release. Progress, architectural
decisions, and acceptance criteria live in [MEMORY.md](MEMORY.md).

## Safe local quick start

Prerequisites:

- Python 3.10 or newer;
- Node.js 22.12 or newer and npm;
- a reachable LLM provider. Ollama is the default local development provider.

Create an isolated backend environment and local configuration:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows, activate the environment with `venv\Scripts\activate`. Review `.env` before startup
and configure only the provider you intend to use. Do not commit `.env` or API keys. For the
default Ollama configuration, make sure the configured model is installed and the Ollama service
is running.

Install the locked frontend dependencies:

```bash
cd frontend
npm ci
cd ..
```

Run the backend on loopback in one terminal:

```bash
source venv/bin/activate
python scripts/launch.py local --host 127.0.0.1 --reload
```

Run the frontend in another terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. API documentation is at `http://127.0.0.1:8000/docs`.

To serve a production-style frontend and API from one local port, build the frontend first and
then start the backend without `--reload`:

```bash
cd frontend
npm ci
npm run build
cd ..
source venv/bin/activate
python scripts/launch.py local --host 127.0.0.1
```

Then open `http://127.0.0.1:8000`.

### Authentication and network exposure

Authentication is off in the development example so loopback setup stays simple. Before binding
to a non-loopback address, enable it and provide separate scoped credentials in `.env` or copy the
registry template from [config/api_tokens.json.example](config/api_tokens.json.example):

```env
API_AUTH_ENABLED=true
API_AUTH_TOKENS=local-chat|chat:replace-this,local-ops|ops:replace-this-too
CORS_ALLOW_ORIGINS=https://your-ui.example
```

An enabled authentication configuration with no valid token fails closed. Treat all tokens as
secrets. Production configuration also requires Redis-backed sessions; development defaults to
ephemeral process memory.

## Operations

The canonical health endpoints are:

| Endpoint | Access | Meaning |
| --- | --- | --- |
| `GET /livez` | Public | Minimal process liveness |
| `GET /readyz` | Public | Minimal readiness; returns `503` when dependencies are not ready |
| `GET /ops/health` | `ops` scope when auth is enabled | Detailed runtime diagnostics |

`/health`, `/health/live`, and `/health/ready` remain deprecated compatibility aliases. Detailed
health and metrics may reveal operational information and should not be exposed without access
control.

## Verification

After installing backend and frontend dependencies, run the repository checks with:

```bash
./scripts/run_linter.sh
```

This checks formatting, linting, strict backend/script types, backend tests, and the frontend
production build. Passing tests establishes the behaviours they cover; it does not guarantee
factual accuracy, character fidelity, content safety, or legal permission to use a dataset.

## Migration, privacy, and content rights

- The repository may still contain legacy third-party character data, scripts, or artwork awaiting
  Phase 1 migration. Treat those files as private migration inputs unless you have independently
  verified redistribution rights. The code licence does not grant rights to third-party content.
- Only import material you own, have licensed, or may lawfully use. Preserve source, licence,
  rights basis, safety review, and content hashes in every Character Pack.
- Cloud LLM providers may receive user messages, prompts, and retrieved excerpts. Obtain informed
  consent and review the provider's retention and data-use terms before sending sensitive content.
- The 0.7 session layer is compatibility infrastructure, not a complete privacy system. Durable
  memory, user export/deletion, consent, and retention controls remain migration work.
- Telegram and other external transports require explicit operator and participant authorisation.
  Do not connect this development runtime to real communities as an autonomous agent.
- Removing files in a future release will not erase them from Git history. History rewriting,
  credential rotation, and public redistribution require separate operational decisions.

This is an engineering migration notice, not legal advice.

## Repository map

```text
src/                 FastAPI compatibility runtime and new knowledge foundations
frontend/            Vue/Vite compatibility clients
src/knowledge/       Character Pack validation and immutable Artifact helpers
docs/                migration-era formats and operating notes
scripts/             launch, migration, evaluation, and repository checks
tests/               backend and ASGI regression tests
MEMORY.md            long-lived roadmap, decisions, and implementation log
```

The source code is distributed under [GPL-3.0](LICENSE). Review content rights separately from the
software licence.
