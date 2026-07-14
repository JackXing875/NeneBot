"""Read-only operations API for the Pack-driven runtime."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.auth import configured_auth_identities, require_api_scope
from src.core.config import settings
from src.core.metrics import registry
from src.core.observability import build_health_payload
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.knowledge.artifacts import ArtifactStore, PublishedArtifact
from src.knowledge.runtime import RuntimeCharacter
from src.runtime import check_session_backend
from src.services.session_store import InMemorySessionStore, SessionStore
from src.services.session_store_redis import RedisSessionStore

admin_router = APIRouter(
    prefix="/admin/api",
    tags=["Admin"],
    dependencies=[Depends(require_api_scope("ops"))],
)


def _session_summary(session_store: SessionStore) -> dict[str, object]:
    backend_name = getattr(session_store, "backend_name", "unknown")
    summary: dict[str, object] = {
        "backend": backend_name,
        "ttl_seconds": settings.session_ttl_seconds,
    }

    if isinstance(session_store, InMemorySessionStore):
        summary["session_count"] = len(session_store._sessions)
    elif isinstance(session_store, RedisSessionStore):
        summary["key_prefix"] = session_store.key_prefix

    return summary


def _published_artifact_summary(artifact: PublishedArtifact) -> dict[str, object]:
    manifest = artifact.manifest
    return {
        "artifact_version": manifest.artifact_version,
        "artifact_hash": manifest.artifact_hash,
        "created_at": manifest.created_at,
        "pack_version": manifest.pack_version,
        "pack_content_hash": manifest.pack_content_hash,
        "embedding_model": manifest.embedding_model,
        "vector_dimension": manifest.vector_dimension,
        "record_count": manifest.record_count,
        "manifest_sha256": artifact.manifest_sha256,
        "path": str(artifact.path),
    }


def _pack_summary(
    character: RuntimeCharacter | None,
    artifact: PublishedArtifact | None,
) -> dict[str, object]:
    if character is None or artifact is None:
        return {"status": "unavailable"}
    provenance = character.provenance
    return {
        "status": "active",
        "pack_id": character.pack_id,
        "version": character.pack_version,
        "display_name": character.display_name,
        "default_locale": character.default_locale,
        "content_hash": character.pack_content_hash,
        "provenance": provenance.model_dump(mode="json"),
        "theme": character.theme.model_dump(mode="json"),
        "artifact": _published_artifact_summary(artifact),
    }


def _artifact_versions(pack_id: str) -> list[dict[str, object]]:
    versions = ArtifactStore(settings.artifact_store_path).list_versions(pack_id)
    return [_published_artifact_summary(item) for item in versions]


def _runtime_state(request: Request) -> tuple[RuntimeCharacter | None, PublishedArtifact | None]:
    character = getattr(request.app.state, "character", None)
    artifact = getattr(request.app.state, "artifact", None)
    return character, artifact


@admin_router.get("/overview")
async def admin_overview(request: Request) -> dict[str, object]:
    app = request.app
    vector_store: FaissVectorStore = app.state.vector_store
    session_store: SessionStore = app.state.session_store
    character, artifact = _runtime_state(request)
    frontend_dist = Path(settings.frontend_dist_dir)
    session_ok, session_error = check_session_backend(session_store)

    health = build_health_payload(
        vector_store=vector_store,
        frontend_dist_exists=frontend_dist.exists(),
        session_backend_name=getattr(session_store, "backend_name", "unknown"),
        session_backend_ok=session_ok,
        session_backend_error=session_error,
        character=character,
        artifact=artifact,
    )

    return {
        "service": {
            "name": settings.api_title,
            "version": settings.api_version,
            "environment": settings.app_env,
            "request_id": getattr(request.state, "request_id", None),
        },
        "health": health,
        "pack": _pack_summary(character, artifact),
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.effective_llm_model,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_retries": settings.llm_max_retries,
        },
        "sessions": _session_summary(session_store),
        "retrieval": {
            "match_threshold": settings.match_threshold,
            "vector_dimension": getattr(vector_store, "dimension", None),
            "index_vectors": vector_store.index.ntotal,
            "metadata_records": len(vector_store.metadata),
        },
        "auth": {
            "enabled": settings.api_auth_enabled,
            "identities": [
                {"name": identity.name, "scopes": sorted(identity.scopes)}
                for identity in configured_auth_identities()
            ],
        },
        "integrations": {
            "telegram_enabled": bool(settings.telegram_bot_token),
            "telegram_mode": settings.telegram_mode,
            "metrics_enabled": settings.metrics_enabled,
            "tracing_enabled": settings.tracing_enabled,
            "tracing_exporter": settings.tracing_exporter,
        },
    }


@admin_router.get("/metrics/summary")
async def admin_metrics_summary() -> dict[str, object]:
    rendered = registry.render()
    lines = [line for line in rendered.splitlines() if line and not line.startswith("#")]
    return {
        "metric_series_count": len(lines),
        "preview": lines[:20],
    }


@admin_router.get("/knowledge/overview")
async def admin_knowledge_overview(request: Request) -> dict[str, Any]:
    """Describe the active artifact without exposing a runtime mutation path."""
    vector_store: FaissVectorStore = request.app.state.vector_store
    character, artifact = _runtime_state(request)
    versions = _artifact_versions(character.pack_id) if character is not None else []
    return {
        "pack": _pack_summary(character, artifact),
        "versions": versions,
        "vector_store": {
            "index_vectors": vector_store.index.ntotal,
            "metadata_records": len(vector_store.metadata),
        },
        "operations": {
            "mode": "offline_artifacts_only",
            "mutable": False,
            "commands": {
                "validate": "persona pack validate <pack-dir>",
                "build": "persona pack build <pack-dir>",
                "eval": "persona pack eval <pack-dir>",
                "promote": "persona pack promote <pack-id> <artifact-reference>",
                "rollback": "persona pack rollback <pack-id>",
            },
        },
    }


def _retired_mutation_endpoint() -> None:
    raise HTTPException(
        status_code=410,
        detail=(
            "Online knowledge mutation was removed. Validate, build, evaluate, and promote "
            "an immutable Character Pack artifact with the `persona pack` CLI."
        ),
    )


@admin_router.post("/knowledge/rebuild", deprecated=True)
async def admin_knowledge_rebuild() -> None:
    """Compatibility tombstone for the removed online rebuild operation."""
    _retired_mutation_endpoint()


@admin_router.post("/knowledge/import", deprecated=True)
async def admin_knowledge_import() -> None:
    """Compatibility tombstone for the removed online import operation."""
    _retired_mutation_endpoint()
