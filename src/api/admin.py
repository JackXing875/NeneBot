"""Admin API for operations, configuration introspection, and knowledge workflows."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.audit import audit_log
from src.core.auth import configured_auth_identities, require_api_scope
from src.core.config import settings
from src.core.metrics import registry
from src.core.observability import build_health_payload
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.runtime import check_session_backend
from src.services.knowledge_base_admin import (
    rebuild_knowledge_base,
    summarize_dataset,
    write_jsonl_dataset,
)
from src.services.session_store import InMemorySessionStore, SessionStore
from src.services.session_store_redis import RedisSessionStore

admin_router = APIRouter(
    prefix="/admin/api",
    tags=["Admin"],
    dependencies=[Depends(require_api_scope("ops"))],
)


class KnowledgeImportRequest(BaseModel):
    content: str = Field(..., min_length=1, description="JSONL dataset content.")
    rebuild: bool = Field(
        True,
        description="Whether to rebuild the vector index immediately after import.",
    )
    dry_run: bool = Field(
        False,
        description="Validate dataset content without writing it to disk.",
    )


class KnowledgeActionResponse(BaseModel):
    dataset: dict[str, Any]
    vector_store: dict[str, Any] | None = None
    dry_run: bool = False


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


def _refresh_vector_store(request: Request) -> dict[str, Any]:
    vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )
    request.app.state.vector_store = vector_store
    request.app.state.rag_pipeline.vector_store = vector_store
    return {
        "index_vectors": vector_store.index.ntotal,
        "metadata_records": len(vector_store.metadata),
        "index_path": vector_store.index_path,
        "metadata_path": vector_store.meta_path,
    }


@admin_router.get("/overview")
async def admin_overview(request: Request) -> dict[str, object]:
    app = request.app
    vector_store: FaissVectorStore = app.state.vector_store
    session_store: SessionStore = app.state.session_store
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    session_ok, session_error = check_session_backend(session_store)

    health = build_health_payload(
        vector_store=vector_store,
        frontend_dist_exists=frontend_dist.exists(),
        session_backend_name=getattr(session_store, "backend_name", "unknown"),
        session_backend_ok=session_ok,
        session_backend_error=session_error,
    )

    provider_model = (
        settings.claude_model_name
        if settings.llm_provider == "claude"
        else settings.openai_compat_model
        if settings.llm_provider in ("deepseek", "openai")
        else settings.llm_model_name
    )

    return {
        "service": {
            "name": settings.api_title,
            "version": settings.api_version,
            "environment": settings.app_env,
            "request_id": getattr(request.state, "request_id", None),
        },
        "health": health,
        "llm": {
            "provider": settings.llm_provider,
            "model": provider_model,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_retries": settings.llm_max_retries,
        },
        "sessions": _session_summary(session_store),
        "retrieval": {
            "match_threshold": settings.match_threshold,
            "vector_dim": settings.vector_dim,
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
    vector_store: FaissVectorStore = request.app.state.vector_store
    return {
        "dataset": summarize_dataset(settings.data_path),
        "vector_store": {
            "index_vectors": vector_store.index.ntotal,
            "metadata_records": len(vector_store.metadata),
            "index_path": vector_store.index_path,
            "metadata_path": vector_store.meta_path,
        },
    }


@admin_router.post("/knowledge/rebuild", response_model=KnowledgeActionResponse)
async def admin_knowledge_rebuild(request: Request) -> KnowledgeActionResponse:
    audit_log(
        "admin_knowledge_rebuild_requested",
        request=request,
        action="knowledge_rebuild",
        endpoint="/admin/api/knowledge/rebuild",
        dataset_path=settings.data_path,
    )
    try:
        rebuild_knowledge_base()
        vector_summary = _refresh_vector_store(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Knowledge rebuild failed: {exc}") from exc

    return KnowledgeActionResponse(
        dataset=summarize_dataset(settings.data_path),
        vector_store=vector_summary,
    )


@admin_router.post("/knowledge/import", response_model=KnowledgeActionResponse)
async def admin_knowledge_import(
    payload: KnowledgeImportRequest,
    request: Request,
) -> KnowledgeActionResponse:
    audit_log(
        "admin_knowledge_import_requested",
        request=request,
        action="knowledge_import",
        endpoint="/admin/api/knowledge/import",
        rebuild_requested=payload.rebuild,
        dry_run=payload.dry_run,
        dataset_path=settings.data_path,
    )
    try:
        if payload.dry_run:
            from src.services.knowledge_base_admin import validate_jsonl_content

            validate_jsonl_content(payload.content)
            dataset_summary = summarize_dataset(settings.data_path)
        else:
            dataset_summary = write_jsonl_dataset(payload.content, settings.data_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    vector_summary: dict[str, Any] | None = None
    if payload.rebuild and not payload.dry_run:
        try:
            rebuild_knowledge_base()
            vector_summary = _refresh_vector_store(request)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Dataset saved but rebuild failed: {exc}",
            ) from exc

    return KnowledgeActionResponse(
        dataset=dataset_summary,
        vector_store=vector_summary,
        dry_run=payload.dry_run,
    )
