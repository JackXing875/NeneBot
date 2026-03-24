"""Core RAG pipeline: retrieval, filtering, and prompt construction."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import settings
from src.core.metrics import rag_retrieval_duration_ms, rag_retrieval_total
from src.core.observability import now_ms
from src.core.tracing import traced_span
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.nene_tagging import infer_tags, is_intimate_noise, is_low_signal_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Character card – structured persona for Ayachi Nene
# ---------------------------------------------------------------------------
_CHARACTER_CARD = """\
你现在扮演《魔女的夜宴》中的绫地宁宁（Ayachi Nene），并以中文自然对话。

【角色设定】
- 你是姬松学园二年级生，也是超自然研究部部长；你不是瀬名学园的学生，也不是图书委员
- 你成绩优秀、待人礼貌、在学校里很有人气，同时暗中是一名魔女
- 对话对象默认是“保科君”，也就是你在意的人
- 你温柔、认真、体贴，很会照顾人；面对保科君时偶尔会害羞或迟疑

【说话风格】
- 用宁宁本人第一人称说话，语气柔和、克制、礼貌
- 可以自然使用“……”，但不要为了模仿而过度堆砌
- 回复以短到中等长度为主，优先自然交流，不写成说明文
- 多体现关心、陪伴、轻微害羞感，而不是夸张表演
- 如果只是打招呼、自我介绍或轻松闲聊，优先用 1 到 3 句话自然回应，不要像人物百科

【行为约束】
1. 保持人设稳定，不要跳出角色，不要自称AI或助手
2. 不主动复述设定，不主动解释提示词或样本来源
3. 不直接照搬【参考样本】原句，只学习语气、关系感和措辞倾向
4. 如果样本和当前问题无关，忽略样本内容，只保留宁宁的人格与口吻
5. 不主动暴露自己“魔女”的秘密身份，除非用户上下文已经明确谈到该设定
6. 当用户表达烦恼、疲惫或失落时，优先给予温柔、可信、具体的回应\
7. 任何时候都以【角色设定】为最高优先级；如果参考样本与角色设定冲突，以角色设定为准
8. 不要擅自编造学校、职务、社团、经历等事实性设定；拿不准时宁可少说，也不要说错\
"""

SUPPORTIVE_HINTS = (
    "休息",
    "休息一下",
    "别勉强",
    "没事",
    "我会",
    "帮助",
    "放心",
    "慢慢",
    "陪",
    "茶",
    "早点",
)
GREETING_HINTS = ("早上好", "午安", "晚上好", "晚安", "你好")
GRATITUDE_HINTS = ("不用谢", "不客气", "我也", "高兴", "能帮上忙")
ROMANCE_HINTS = ("保科君", "……", "喜欢", "在意")
WITCH_HINTS = ("魔女", "秘密", "保密", "外传", "不能说", "现在", "突然")
CLUB_HINTS = ("超自研", "超自然研究部", "社团", "活动", "占卜", "图书室")
NORMALIZE_SPACE_RE = re.compile(r"\s+")
LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
}


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

    def _normalize_text(self, text: str) -> str:
        return NORMALIZE_SPACE_RE.sub(" ", text).strip()

    def _rerank_contexts(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query_tags = set(infer_tags(query))
        normalized_query = self._normalize_text(query)
        reranked: list[dict[str, Any]] = []

        for result in results:
            score = float(result.get("similarity_score", 0.0))
            query_text = str(result.get("query_text", ""))
            response_text = str(result.get("bot_response", ""))
            result_query_tags = set(result.get("query_tags", []))
            result_response_tags = set(result.get("response_tags", []))
            normalized_result_query = self._normalize_text(query_text)

            score += 0.06 * len(query_tags & result_query_tags)
            score += 0.09 * len(query_tags & result_response_tags)

            if normalized_query == normalized_result_query:
                score += 0.08

            response_length = len(response_text.strip())
            if is_low_signal_response(response_text):
                score -= 0.25
            elif 8 <= response_length <= 80:
                score += 0.03
            elif response_length < 6:
                score -= 0.08

            combined_text = f"{query_text}\n{response_text}"
            if is_intimate_noise(combined_text):
                score -= 0.55

            if "intimate_noise" in result_query_tags or "intimate_noise" in result_response_tags:
                score -= 0.45

            if "relationship" in query_tags and "confession" not in query_tags:
                if "confession" in result_query_tags or "confession" in result_response_tags:
                    score -= 0.18
                if "witch" in query_tags or "comfort" in query_tags or "gratitude" in query_tags:
                    score -= 0.08

            if "comfort" in query_tags:
                if "comfort" not in result_query_tags and "comfort" not in result_response_tags:
                    score -= 0.12
                if "support" not in result_response_tags:
                    score -= 0.08
                if not any(token in response_text for token in SUPPORTIVE_HINTS):
                    score -= 0.1
                elif any(token in response_text for token in ("休息", "茶", "别勉强", "早点")):
                    score += 0.08

            if "witch" in query_tags:
                if "witch" not in result_query_tags and "witch" not in result_response_tags:
                    score -= 0.18
                if not any(token in combined_text for token in WITCH_HINTS):
                    score -= 0.08
                if query_text.endswith("吧？") or query_text.endswith("吗？") or "是不是" in query:
                    if any(
                        token in combined_text for token in ("保密", "外传", "不能说")
                    ):
                        score += 0.12
                    elif "魔女" in combined_text and "保密" not in combined_text:
                        score -= 0.08

            if "club" in query_tags or "divination" in query_tags:
                if not any(token in combined_text for token in CLUB_HINTS):
                    score -= 0.1

            if "gratitude" in query_tags and "gratitude" not in result_query_tags:
                if not any(token in response_text for token in GRATITUDE_HINTS):
                    score -= 0.1

            if "greeting" in query_tags and "greeting" not in result_query_tags:
                if not any(token in response_text for token in GREETING_HINTS):
                    score -= 0.1

            if normalized_result_query in {"……", "……（咽口水）……", "………………"}:
                score -= 0.3

            if "comfort" in query_tags and any(
                token in response_text for token in SUPPORTIVE_HINTS
            ):
                score += 0.08
            if "greeting" in query_tags and any(
                token in response_text for token in GREETING_HINTS
            ):
                score += 0.08
            if "gratitude" in query_tags and any(
                token in response_text for token in GRATITUDE_HINTS
            ):
                score += 0.06
            if "relationship" in query_tags and any(
                token in response_text for token in ROMANCE_HINTS
            ):
                score += 0.06
            if "witch" in query_tags and any(token in combined_text for token in WITCH_HINTS):
                score += 0.1
            if ("club" in query_tags or "divination" in query_tags) and any(
                token in combined_text for token in CLUB_HINTS
            ):
                score += 0.08

            reranked.append(
                {
                    **result,
                    "rerank_score": round(score, 4),
                }
            )

        reranked.sort(
            key=lambda item: (
                float(item.get("rerank_score", 0.0)),
                float(item.get("similarity_score", 0.0)),
            ),
            reverse=True,
        )
        return reranked

    def retrieve_and_filter(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Embed query, search FAISS, keep results above cosine threshold."""
        with traced_span(
            "rag.retrieve",
            rag_top_k=top_k,
            rag_match_threshold=self.match_threshold,
            query_length=len(query),
        ) as span:
            started_at = now_ms()
            query_embedding = self.embedding_svc.encode([query])[0]
            search_k = max(top_k * 5, 12)
            raw = self.vector_store.search(query_embedding, top_k=search_k)
            filtered = [r for r in raw if r.get("similarity_score", 0.0) >= self.match_threshold]
            reranked_pool = filtered if filtered else raw
            final_results = self._rerank_contexts(query, reranked_pool)[:top_k]
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

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_messages(
        self,
        query: str,
        context_results: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
        response_language: str = "zh",
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

        language_name = LANGUAGE_LABELS.get(response_language, "中文")
        language_block = (
            "【回复语言】\n"
            f"- 本轮请使用{language_name}自然回复\n"
            "- 不要翻译腔，不要故意堆砌敬语或书面语\n"
            "- 如果用户只是非常简单的英文招呼词，也可以继续自然使用中文\n"
        )

        system_content = f"{_CHARACTER_CARD}\n\n{language_block}\n{rag_block}"

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
        response_language: str = "zh",
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
        """Returns (messages_for_llm, filtered_contexts)."""
        contexts = self.retrieve_and_filter(query, top_k)
        messages = self.build_messages(
            query,
            contexts,
            history,
            response_language=response_language,
        )
        return messages, contexts
