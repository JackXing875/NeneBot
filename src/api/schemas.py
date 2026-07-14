"""Pydantic schemas for API request and response validation."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.knowledge.pack import PackTheme, Provenance
from src.services.session_store import MAX_SESSION_ID_LENGTH, validate_session_id

MAX_QUERY_LENGTH = 4_000


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="The user's input text.",
    )
    session_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_SESSION_ID_LENGTH,
        description="Session ID for multi-turn memory. Omit to start a new session.",
    )
    top_k: int = Field(3, description="Number of RAG references to retrieve.", ge=1, le=10)

    @field_validator("query", mode="before")
    @classmethod
    def _normalize_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("session_id")
    @classmethod
    def _validate_public_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_session_id(value, allow_telegram=False)


class ReferenceMeta(BaseModel):
    record_id: str | None = None
    content_sha256: str | None = None
    pack_id: str | None = None
    pack_version: str | None = None
    historical_query: str
    bot_response: str
    similarity_score: float = Field(..., description="Cosine similarity (0–1, higher = better).")
    source: str | None = None
    license: str | None = None
    safety_classification: str | None = None


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Generated response from the active Character Pack.")
    session_id: str = Field(..., description="Session ID; pass back on subsequent turns.")
    references: List[ReferenceMeta] = Field(default_factory=list, description="RAG context used.")


class CharacterResponse(BaseModel):
    """Public, non-secret descriptor for the active Character Pack."""

    pack_id: str
    pack_version: str
    pack_content_hash: str
    display_name: str
    default_locale: str
    theme: PackTheme
    provenance: Provenance
