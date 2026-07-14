"""Pack-driven retrieval and prompt construction for the compatibility chat API."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.core.config import settings
from src.core.metrics import rag_retrieval_duration_ms, rag_retrieval_total
from src.core.observability import now_ms
from src.core.tracing import traced_span
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.knowledge.runtime import RuntimeCharacter
from src.services.embedding_svc import EmbeddingService

logger = logging.getLogger(__name__)

LANGUAGE_LABELS = {
    "zh": "简体中文",
    "en": "English",
    "ja": "日本語",
}
NORMALIZE_SPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")


class RAGPipeline:
    """Retrieve Pack records and compile the one authoritative system prompt."""

    def __init__(
        self,
        vector_store: FaissVectorStore,
        embedding_svc: EmbeddingService,
        character: RuntimeCharacter,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_svc = embedding_svc
        self.character = character
        self.match_threshold = settings.match_threshold

    @staticmethod
    def _normalize_text(text: str) -> str:
        return NORMALIZE_SPACE_RE.sub(" ", text).strip().casefold()

    @classmethod
    def _lexical_overlap(cls, query: str, candidate: str) -> int:
        query_tokens = set(WORD_RE.findall(cls._normalize_text(query)))
        candidate_tokens = set(WORD_RE.findall(cls._normalize_text(candidate)))
        return len(query_tokens & candidate_tokens)

    def _rerank_contexts(self, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply small, content-neutral exact/lexical bonuses after semantic search."""
        normalized_query = self._normalize_text(query)
        reranked: list[dict[str, Any]] = []
        for result in results:
            candidate = str(result.get("query_text", ""))
            score = float(result.get("similarity_score", 0.0))
            if normalized_query == self._normalize_text(candidate):
                score += 0.08
            score += min(self._lexical_overlap(query, candidate) * 0.01, 0.08)
            reranked.append({**result, "rerank_score": round(score, 4)})
        reranked.sort(
            key=lambda item: (
                float(item.get("rerank_score", 0.0)),
                float(item.get("similarity_score", 0.0)),
                str(item.get("record_id", "")),
            ),
            reverse=True,
        )
        return reranked

    def retrieve_and_filter(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Embed a query and return only records above the configured threshold."""
        with traced_span(
            "rag.retrieve",
            pack_id=self.character.pack_id,
            pack_version=self.character.pack_version,
            rag_top_k=top_k,
            rag_match_threshold=self.match_threshold,
            query_length=len(query),
        ) as span:
            started_at = now_ms()
            query_embedding = self.embedding_svc.encode([query])[0]
            raw = self.vector_store.search(query_embedding, top_k=max(top_k * 4, 12))
            filtered = [
                result
                for result in raw
                if float(result.get("similarity_score", 0.0)) >= self.match_threshold
            ]
            final_results = self._rerank_contexts(query, filtered)[:top_k]
            duration_ms = round(now_ms() - started_at, 2)
            rag_retrieval_total.inc(top_k=str(top_k))
            rag_retrieval_duration_ms.observe(duration_ms, top_k=str(top_k))
            logger.info(
                "rag_retrieval_completed",
                extra={
                    "event": "rag_retrieval_completed",
                    "pack_id": self.character.pack_id,
                    "pack_version": self.character.pack_version,
                    "query_length": len(query),
                    "top_k": top_k,
                    "retrieved_count": len(raw),
                    "filtered_count": len(filtered),
                    "final_count": len(final_results),
                    "match_threshold": self.match_threshold,
                    "duration_ms": duration_ms,
                },
            )
            if span is not None:
                span.set_attribute("rag.retrieved_count", len(raw))
                span.set_attribute("rag.filtered_count", len(filtered))
                span.set_attribute("rag.final_count", len(final_results))
                span.set_attribute("rag.duration_ms", duration_ms)
            return final_results

    @staticmethod
    def _reference_block(context_results: list[dict[str, Any]]) -> str:
        if not context_results:
            return "【参考记录】\n没有达到相似度阈值的已审核记录；不要虚构 Pack 事实。"

        entries: list[str] = []
        for index, result in enumerate(context_results, start=1):
            provenance = result.get("provenance", {})
            source = (
                provenance.get("source", "unknown") if isinstance(provenance, dict) else "unknown"
            )
            license_name = (
                provenance.get("license", "unknown") if isinstance(provenance, dict) else "unknown"
            )
            entries.append(
                "\n".join(
                    [
                        f"记录 {index} [id={result.get('record_id', 'unknown')}; "
                        f"similarity={float(result.get('similarity_score', 0.0)):.3f}; "
                        f"source={source}; license={license_name}]",
                        f"用户示例：{result.get('query_text', '')}",
                        f"角色回复示例：{result.get('bot_response', '')}",
                    ]
                )
            )
        return "【参考记录】\n" + "\n\n".join(entries)

    def build_messages(
        self,
        query: str,
        context_results: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
        response_language: str = "zh",
    ) -> list[dict[str, str]]:
        """Compile Pack prompt, persona, language, and reviewed references."""
        language_name = LANGUAGE_LABELS.get(response_language, "简体中文")
        system_content = "\n\n".join(
            [
                self.character.prompt.strip(),
                f"【角色资料：{self.character.display_name}】\n{self.character.persona.strip()}",
                f"【回复语言】\n本轮使用 {language_name} 自然回复；除非用户要求，不解释语言选择。",
                self._reference_block(context_results),
            ]
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        return messages

    def process_query(
        self,
        query: str,
        top_k: int = 3,
        history: list[dict[str, str]] | None = None,
        response_language: str = "zh",
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """Return provider messages and the exact Pack records used as context."""
        contexts = self.retrieve_and_filter(query, top_k)
        return (
            self.build_messages(
                query,
                contexts,
                history,
                response_language=response_language,
            ),
            contexts,
        )
