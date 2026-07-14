# Persona Studio

> A local-first, rights-aware Character Pack runtime with traceable retrieval artifacts.

[中文说明](README_ch.md) · [Character Pack v1](docs/character-packs.md) ·
[Private migration guide](docs/private-pack-migration.md) · [Roadmap](MEMORY.md)

Persona Studio separates authored character content from the chat runtime. Persona, prompt,
knowledge, retrieval evaluation, theme, provenance, licence and safety review live in one strict
Character Pack. An offline builder compiles the Pack into a verified FAISS Artifact; the web and
Telegram runtimes only read an explicitly promoted Artifact.

The repository includes one original, CC0-licensed demo Pack: **Mira**, a fictional night guide
for an imaginary archive. It uses a code-native initials avatar and contains no third-party
character art or dialogue corpus.

## Phase 1 capabilities

- strict Pack validation with duplicate-key, path traversal, symlink, size and schema checks;
- canonical per-record and whole-Pack SHA-256 hashes;
- mandatory source, licence, rights basis and completed safety review on every knowledge record;
- offline FAISS build with provenance preserved in retrieval metadata;
- deterministic retrieval evaluation shipped with the Pack;
- content-addressed Artifact versions, integrity verification, atomic promotion and rollback;
- exact-source removal by deriving a new Pack version, followed by the same build workflow;
- read-only `/v1/chat`, `/v1/chat/stream` and `/v1/character` runtime surfaces;
- reference metadata in synchronous and SSE responses;
- a code-native Vue client and read-only Artifact operations panel.

The retired online knowledge import and rebuild URLs return HTTP `410`. Content cannot bypass the
Pack and Artifact boundary.

## Quick start

Requirements: Python 3.10+, Node.js 22.12+, npm, and a reachable configured LLM provider. Ollama
is the development default.

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
cp .env.example .env

cd frontend
npm ci
cd ..
```

Build, evaluate and activate the demo Pack before starting the runtime:

```bash
persona pack validate packs/demo
persona pack build packs/demo
persona pack promote mira-demo 1.0.0
persona pack eval packs/demo
```

Start backend and frontend together:

```bash
persona dev --host 127.0.0.1
```

Open `http://localhost:5173`. The API is on `http://127.0.0.1:8000`; API documentation is at
`/docs`. `persona local --host 127.0.0.1` starts only the backend.

## Pack release workflow

```bash
# 1. Validate authored inputs.
persona pack validate path/to/pack

# 2. Install an immutable artifact without changing the active runtime.
persona pack build path/to/pack --artifact-version 1.1.0

# 3. Promote by exact version, full hash, or artifact directory name.
persona pack promote my-pack 1.1.0

# 4. Evaluate the active artifact against the Pack fixtures.
persona pack eval path/to/pack

# 5. Return to the immediately preceding installed version.
persona pack rollback my-pack
```

To remove records from an exact provenance source, derive a new Pack rather than mutating an
active index:

```bash
persona pack derive private/my-pack \
  --exclude-source "licensed/source-a.jsonl" \
  --output private/my-pack-1.2.0 \
  --version 1.2.0
persona pack build private/my-pack-1.2.0
```

`private/`, `packs/private/` and generated `artifacts/` are ignored. The source Pack is never
modified by `derive`.

## API and operations

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/character` | Active Pack identity, theme and rights metadata |
| `POST /v1/chat` | Compatibility chat API with traceable references |
| `POST /v1/chat/stream` | SSE chat with metadata, chunks, error and done events |
| `GET /livez` | Public process liveness |
| `GET /readyz` | Public minimal readiness |
| `GET /ops/health` | Protected detailed diagnostics |
| `GET /admin/api/knowledge/overview` | Protected read-only Artifact/version view |

When authentication is enabled, use separate `chat` and `ops` scoped credentials. Production
configuration requires Redis sessions. Cloud LLM providers may receive user messages, Pack
prompts and retrieved excerpts; obtain informed consent and review provider retention terms.

## Verification

```bash
./scripts/run_linter.sh
```

This runs Ruff formatting/linting, strict mypy, backend tests, and a production frontend build.
Tests validate implementation contracts, not the factual accuracy or legal status of content you
add. Only publish material you own, have licensed, or may lawfully use.

## Repository map

```text
packs/demo/          Original public demo Pack
src/knowledge/       Pack, builder, Artifact store and runtime contracts
src/                 FastAPI runtime and adapters
frontend/            Pack-driven chat and read-only operations UI
docs/                Format and private migration guidance
tests/               Unit, ASGI and end-to-end contract tests
MEMORY.md            Long-lived roadmap and implementation record
```

Source code is licensed under [GPL-3.0](LICENSE). Pack content carries its own explicit licence
and provenance.
