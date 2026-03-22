# Changelog

## v0.6.0b1

Preview release focused on production groundwork and admin operations.

### Added

- Redis-backed session persistence with memory fallback.
- Structured logging, request IDs, health endpoints, metrics, and optional tracing.
- API token auth with named identities and scope separation for `chat` and `ops`.
- Telegram adapter with polling and webhook support.
- Read-only admin console at `/admin`.
- Knowledge base admin workflow:
  - dataset overview
  - JSONL dry-run validation
  - dataset import
  - vector index rebuild
- Release checklist for preview validation.

### Improved

- LLM timeout / retry / failure handling and metrics.
- Environment layering via `APP_ENV`.
- Test coverage for auth, admin, metrics, tracing, Telegram, and resilience flows.

### Notes

- This is a preview/beta-style release, not a final stable release.
- Recommended validation path:
  - run `ruff`
  - run `pytest`
  - build frontend
  - verify `/admin` and knowledge workflows
