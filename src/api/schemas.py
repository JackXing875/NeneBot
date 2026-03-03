"""Pydantic schemas for API request and response validation."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema for incoming chat requests from the user."""
    query: str = Field(..., description="The user's input text.", example="要是惹你不快的话我道歉，抱歉")
    top_k: int = Field(3, description="Number of historical references to retrieve.", ge=1, le=5)


class ReferenceMeta(BaseModel):
    """Schema for retrieved historical references."""
    historical_query: str
    bot_response: str
    distance_score: float


class ChatResponse(BaseModel):
    """Schema for the API response."""
    reply: str = Field(..., description="The generated response from Ningning.")
    references: List[ReferenceMeta] = Field(default_factory=list, description="The retrieved context used.")
    prompt_used: Optional[str] = Field(None, description="The actual prompt sent to the LLM (for debugging).")