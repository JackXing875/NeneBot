# Release Checklist

## Scope Freeze

- Release target includes only:
  - chat web UI
  - Telegram adapter
  - admin overview
  - metrics / tracing
  - knowledge import / rebuild
- No new feature area is added after freeze.

## Backend Verification

- `./venv/bin/python -m ruff check src tests`
- `./venv/bin/python -m pytest tests`
- `GET /health` works with an `ops` token.
- `GET /metrics` works with an `ops` token.
- `GET /admin/api/overview` works with an `ops` token.

## Frontend Verification

- `cd frontend && npm run build`
- `http://localhost:8000/` loads normally.
- `http://localhost:8000/admin` loads normally.
- Admin page renders overview, identities, metrics, and knowledge panels.

## Knowledge Workflow

- Dry-run validation succeeds on one valid JSONL sample.
- Dry-run validation fails on one invalid JSONL sample.
- Import-only writes dataset successfully.
- Import + rebuild refreshes dataset summary and vector store summary.
- Normal chat still works after rebuild.

## Auth / Ops

- A `chat` token can access `/v1/*`.
- An `ops` token can access `/health*`, `/metrics`, `/admin*`.
- A token without `ops` cannot access `/admin*`.

## Observability

- `/metrics` contains auth, LLM, RAG, and HTTP series.
- Tracing can be enabled with:
  - `TRACING_ENABLED=true`
  - `TRACING_EXPORTER=console`
- Console output shows:
  - `http.request`
  - `rag.retrieve`
  - `llm.request`

## Release Notes

- README and README_ch are updated.
- `.env.example` matches current features.
- Version/tag and changelog entry are prepared.
