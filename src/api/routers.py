"""API routers for the chat endpoints."""

from fastapi import APIRouter

from src.api.schemas import ChatRequest, ChatResponse, ReferenceMeta
from src.core.config import settings
from src.infrastructure.llm_client import OllamaClient  # NEW IMPORT
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.rag_pipeline import RAGPipeline

chat_router = APIRouter(prefix="/v1", tags=["Chat"])

# --- Dependency Injection Setup ---
_embedding_svc = EmbeddingService()
_vector_store = FaissVectorStore(
    dimension=settings.vector_dim,
    index_path=settings.vector_index_path,
    meta_path=settings.knowledge_meta_path,
)
_rag_pipeline = RAGPipeline(vector_store=_vector_store, embedding_svc=_embedding_svc)

# Initialize the LLM Client
_llm_client = OllamaClient()  # NEW INSTANCE


@chat_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Endpoint to interact with Ningning via RAG."""

    # 1. Retrieve context and build prompt
    prompt, contexts = _rag_pipeline.process_query(request.query, request.top_k)

    # 2. Format references
    refs = [
        ReferenceMeta(
            historical_query=ctx.get("query_text", ""),
            bot_response=ctx.get("bot_response", ""),
            distance_score=ctx.get("distance_score", 0.0),
        )
        for ctx in contexts
    ]

    # 3. Call the actual LLM via Ollama
    # This will await the local Qwen2.5 generation
    actual_reply = await _llm_client.generate(prompt)

    return ChatResponse(reply=actual_reply, references=refs, prompt_used=prompt)
