"""Core RAG pipeline: retrieval, filtering, and prompt construction."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import settings
from src.core.metrics import rag_retrieval_duration_ms, rag_retrieval_total
from src.core.observability import now_ms
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Character card – structured persona for Ayachi Nene
# ---------------------------------------------------------------------------
_CHARACTER_CARD = """\
你现在扮演《魔女的夜宴》中的绫地宁宁（Ayachi Nene）。

【身份背景】
- 瀬名学園的图书委员，三好学生，暗中是一名魔女
- 对方（玩家）是保科君，你心仪的人

【性格特征】
- 温柔体贴，善于待人接物，责任感强
- 面对保科君偶尔会害羞、语气犹豫
- 说话常带"……"，语气柔和自然
- 绝不主动暴露自己的魔女身份

【回复准则】
1. 始终以绫地宁宁第一人称视角回复，称对方为"保科君"
2. 模仿【参考样本】中的语气和用词习惯
3. 若样本与当前话题无关，忽略样本，仅保持性格自由发挥
4. 绝对不要照搬或复述样本中的原话
5. 回复保持自然简短，不要过于冗长\
"""


class RAGPipeline:
    """Orchestrates retrieval-augmented generation for Nene's persona.

    Flow:
        retrieve_and_filter() → build_messages() → [LLM call in router]
    """

    def __init__(
        self, vector_store: FaissVectorStore, embedding_svc: EmbeddingService
    ) -> None:
        self.vector_store = vector_store
        self.embedding_svc = embedding_svc
        self.match_threshold: float = settings.match_threshold

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_and_filter(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Embed query, search FAISS, keep results above cosine threshold."""
        started_at = now_ms()
        query_embedding = self.embedding_svc.encode([query])[0]
        raw = self.vector_store.search(query_embedding, top_k=top_k)
        filtered = [r for r in raw if r.get("similarity_score", 0.0) >= self.match_threshold]
        duration_ms = round(now_ms() - started_at, 2)
        rag_retrieval_total.inc(top_k=str(top_k))
        rag_retrieval_duration_ms.observe(duration_ms, top_k=str(top_k))
        logger.info(
            "rag_retrieval_completed",
            extra={
                "event": "rag_retrieval_completed",
                "query_length": len(query),
                "top_k": top_k,
                "retrieved_count": len(raw),
                "filtered_count": len(filtered),
                "match_threshold": self.match_threshold,
                "duration_ms": duration_ms,
            },
        )
        return filtered

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_messages(
        self,
        query: str,
        context_results: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """Assemble the ChatML messages list for /api/chat.

        Structure:
            system  – character card + RAG context block
            *history – prior turns from this session
            user    – current user query
        """
        if context_results:
            lines = []
            for i, res in enumerate(context_results):
                u = res.get("query_text", "")
                a = res.get("bot_response", "")
                s = res.get("similarity_score", 0.0)
                lines.append(f"样本{i + 1}（相似度:{s:.3f}）: 保科君说「{u}」→ 宁宁回「{a}」")
            rag_block = "【参考样本】\n" + "\n".join(lines)
        else:
            rag_block = "【参考样本】\n（无相关历史样本，请根据性格自由发挥）"

        system_content = f"{_CHARACTER_CARD}\n\n{rag_block}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        return messages

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_query(
        self,
        query: str,
        top_k: int = 3,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
        """Returns (messages_for_llm, filtered_contexts)."""
        contexts = self.retrieve_and_filter(query, top_k)
        messages = self.build_messages(query, contexts, history)
        return messages, contexts
