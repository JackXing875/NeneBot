"""Pydantic schemas for API request and response validation."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="The user's input text.")
    session_id: Optional[str] = Field(
        None, description="Session ID for multi-turn memory. Omit to start a new session."
    )
    top_k: int = Field(3, description="Number of RAG references to retrieve.", ge=1, le=10)


class ReferenceMeta(BaseModel):
    historical_query: str
    bot_response: str
    similarity_score: float = Field(..., description="Cosine similarity (0–1, higher = better).")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Generated response from Nene.")
    session_id: str = Field(..., description="Session ID; pass back on subsequent turns.")
    references: List[ReferenceMeta] = Field(
        default_factory=list, description="RAG context used."
    )
