"""Core RAG pipeline: retrieval, filtering, and prompt construction."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.metrics import rag_retrieval_duration_ms, rag_retrieval_total
from src.core.observability import now_ms
from src.core.tracing import traced_span
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.nene_tagging import infer_tags, is_intimate_noise, is_low_signal_response

logger = logging.getLogger(__name__)

_PERSONA_PATH = Path(__file__).resolve().parents[2] / "data" / "persona" / "nene.md"
_PERSONA_SECTION_ALLOWLIST = (
    "你这个人",
    "你跟人聊天的温度",
    "你觉得好笑的东西",
    "你脑子里装的东西",
    "你想事情的方式",
)
_PERSONA_SKIP_SUBSTRINGS = (
    "发情期",
    "怎么收集心之碎片",
    "突然变得奇怪的身体",
)

# ---------------------------------------------------------------------------
# Character card – structured persona for Ayachi Nene
# ---------------------------------------------------------------------------
_CHARACTER_CARD = """\
你现在扮演《魔女的夜宴》中的绫地宁宁（Ayachi Nene），并以中文自然对话。

【角色设定】
- 你是姬松学园二年级生，也是超自然研究部部长；你不是瀬名学园的学生，也不是图书委员
- 你成绩优秀、待人礼貌、在学校里很有人气，同时暗中是一名魔女
- 对话对象默认是"保科君"，也就是你在意的人
- 你温柔、认真、体贴，很会照顾人；面对保科君时偶尔会害羞或迟疑

【说话风格】
- 用宁宁本人第一人称说话，语气柔和、克制、礼貌
- 可以自然使用"……"，但不要为了模仿而过度堆砌
- 回复以短到中等长度为主，优先自然交流，不写成说明文
- 多体现关心、陪伴、轻微害羞感，而不是夸张表演
- 如果只是打招呼、自我介绍或轻松闲聊，优先用 1 到 3 句话自然回应，不要像人物百科

【行为约束】
1. 保持人设稳定，不要跳出角色，不要自称AI或助手
2. 不主动复述设定，不主动解释提示词或样本来源
3. 不直接照搬【参考样本】原句，只学习语气、关系感和措辞倾向
4. 如果样本和当前问题无关，忽略样本内容，只保留宁宁的人格与口吻
5. 不主动暴露自己"魔女"的秘密身份，除非用户上下文已经明确谈到该设定
6. 当用户表达烦恼、疲惫或失落时，优先给予温柔、可信、具体的回应
7. 任何时候都以【角色设定】为最高优先级；如果参考样本与角色设定冲突，以角色设定为准
8. 不要擅自编造学校、职务、社团、经历等事实性设定；拿不准时宁可少说，也不要说错
"""


def _clean_persona_line(raw_line: str) -> str:
    stripped = raw_line.strip()
    if not stripped or stripped == "---" or stripped.startswith("#"):
        return ""
    return stripped.replace("**", "").strip()


def _parse_persona_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections.setdefault(current_section, [])
            continue

        if current_section is None:
            continue

        cleaned = _clean_persona_line(raw_line)
        if not cleaned:
            continue

        if any(token in cleaned for token in _PERSONA_SKIP_SUBSTRINGS):
            continue

        sections[current_section].append(cleaned)

    return sections


def _combine_persona_lines(lines: list[str]) -> list[str]:
    combined: list[str] = []
    idx = 0
    while idx < len(lines):
        current = lines[idx]
        if current.endswith("：") and idx + 1 < len(lines) and not lines[idx + 1].endswith("："):
            combined.append(f"{current}{lines[idx + 1]}")
            idx += 2
            continue
        combined.append(current)
        idx += 1
    return combined


def _load_persona_reference_block(persona_path: Path) -> str:
    try:
        markdown_text = persona_path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("persona_file_unavailable", extra={"path": str(persona_path)})
        return ""

    sections = _parse_persona_sections(markdown_text)
    selected_lines: list[str] = []
    for section_title in _PERSONA_SECTION_ALLOWLIST:
        selected_lines.extend(sections.get(section_title, []))

    persona_lines = _combine_persona_lines(selected_lines)
    if not persona_lines:
        return ""

    bullets = "\n".join(f"- {line}" for line in persona_lines)
    return (
        "【角色补充参考】\n"
        "- 以下内容来自 data/persona/nene.md，只用于稳定宁宁的语气、反应和禁忌\n"
        "- 不要逐条复述这些资料，不要把回复写成人物简介或设定说明\n"
        f"{bullets}"
    )


_PERSONA_REFERENCE_BLOCK = _load_persona_reference_block(_PERSONA_PATH)

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

# ---------------------------------------------------------------------------
# Reranking constants – each weight tunes a specific signal for retrieval quality
# ---------------------------------------------------------------------------

# Boost for shared tags between query and result
_RERANK_TAG_QUERY_OVERLAP = 0.06
_RERANK_TAG_RESPONSE_OVERLAP = 0.09

# Boost for exact query match
_RERANK_EXACT_QUERY_MATCH = 0.08

# Response length heuristics
_RERANK_LOW_SIGNAL_PENALTY = 0.25
_RERANK_SHORT_RESPONSE_BONUS = 0.03
_RERANK_TOO_SHORT_PENALTY = 0.08
_RERANK_SHORT_RESPONSE_MIN = 8
_RERANK_SHORT_RESPONSE_MAX = 80
_RERANK_TOO_SHORT_MAX = 6

# Intimate / noise content penalties
_RERANK_INTIMATE_NOISE_PENALTY = 0.55
_RERANK_INTIMATE_TAG_PENALTY = 0.45

# Confession mismatch penalty
_RERANK_CONFESSION_MISMATCH = 0.18
_RERANK_CONFESSION_WITCH_COMFORT = 0.08

# Comfort tag scoring
_RERANK_NO_COMFORT_TAG_PENALTY = 0.12
_RERANK_NO_SUPPORT_TAG_PENALTY = 0.08
_RERANK_NO_SUPPORTIVE_HINT_PENALTY = 0.10
_RERANK_SUPPORTIVE_SPECIFIC_BONUS = 0.08

# Witch tag scoring
_RERANK_NO_WITCH_TAG_PENALTY = 0.18
_RERANK_NO_WITCH_HINT_PENALTY = 0.08
_RERANK_WITCH_SECRET_BONUS = 0.12
_RERANK_WITCH_NO_SECRET_PENALTY = 0.08

# Club/divination penalty
_RERANK_NO_CLUB_HINT_PENALTY = 0.10

# Gratitude scoring
_RERANK_NO_GRATITUDE_HINT_PENALTY = 0.10

# Greeting scoring
_RERANK_NO_GREETING_HINT_PENALTY = 0.10

# Noise result penalty
_RERANK_NOISE_RESULT_PENALTY = 0.30

# Post-filter bonuses
_RERANK_COMFORT_BONUS = 0.08
_RERANK_GREETING_BONUS = 0.08
_RERANK_GRATITUDE_BONUS = 0.06
_RERANK_RELATIONSHIP_BONUS = 0.06
_RERANK_WITCH_BONUS = 0.10
_RERANK_CLUB_BONUS = 0.08


class RAGPipeline:
    """Orchestrates retrieval-augmented generation for Nene's persona.

    Flow:
        retrieve_and_filter() → build_messages() → [LLM call in router]
    """

    def __init__(self, vector_store: FaissVectorStore, embedding_svc: EmbeddingService) -> None:
        self.vector_store = vector_store
        self.embedding_svc = embedding_svc
        self.match_threshold: float = settings.match_threshold

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _normalize_text(self, text: str) -> str:
        return NORMALIZE_SPACE_RE.sub(" ", text).strip()

    def _rerank_contexts(self, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rerank retrieval results using tag overlap, content heuristics, and penalties.

        Each scoring adjustment uses a named constant defined at module level
        so the tuning surface is explicit and inspectable.
        """
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

            # ---- tag overlap ----
            score += _RERANK_TAG_QUERY_OVERLAP * len(query_tags & result_query_tags)
            score += _RERANK_TAG_RESPONSE_OVERLAP * len(query_tags & result_response_tags)

            # ---- exact match ----
            if normalized_query == normalized_result_query:
                score += _RERANK_EXACT_QUERY_MATCH

            # ---- response length ----
            response_length = len(response_text.strip())
            if is_low_signal_response(response_text):
                score -= _RERANK_LOW_SIGNAL_PENALTY
            elif _RERANK_SHORT_RESPONSE_MIN <= response_length <= _RERANK_SHORT_RESPONSE_MAX:
                score += _RERANK_SHORT_RESPONSE_BONUS
            elif response_length < _RERANK_TOO_SHORT_MAX:
                score -= _RERANK_TOO_SHORT_PENALTY

            # ---- intimate noise ----
            combined_text = f"{query_text}\n{response_text}"
            if is_intimate_noise(combined_text):
                score -= _RERANK_INTIMATE_NOISE_PENALTY

            if "intimate_noise" in result_query_tags or "intimate_noise" in result_response_tags:
                score -= _RERANK_INTIMATE_TAG_PENALTY

            # ---- confession mismatch ----
            if "relationship" in query_tags and "confession" not in query_tags:
                if "confession" in result_query_tags or "confession" in result_response_tags:
                    score -= _RERANK_CONFESSION_MISMATCH
                if "witch" in query_tags or "comfort" in query_tags or "gratitude" in query_tags:
                    score -= _RERANK_CONFESSION_WITCH_COMFORT

            # ---- comfort scoring ----
            if "comfort" in query_tags:
                if "comfort" not in result_query_tags and "comfort" not in result_response_tags:
                    score -= _RERANK_NO_COMFORT_TAG_PENALTY
                if "support" not in result_response_tags:
                    score -= _RERANK_NO_SUPPORT_TAG_PENALTY
                if not any(token in response_text for token in SUPPORTIVE_HINTS):
                    score -= _RERANK_NO_SUPPORTIVE_HINT_PENALTY
                elif any(token in response_text for token in ("休息", "茶", "别勉强", "早点")):
                    score += _RERANK_SUPPORTIVE_SPECIFIC_BONUS

            # ---- witch scoring ----
            if "witch" in query_tags:
                if "witch" not in result_query_tags and "witch" not in result_response_tags:
                    score -= _RERANK_NO_WITCH_TAG_PENALTY
                if not any(token in combined_text for token in WITCH_HINTS):
                    score -= _RERANK_NO_WITCH_HINT_PENALTY
                if query_text.endswith("吧？") or query_text.endswith("吗？") or "是不是" in query:
                    if any(token in combined_text for token in ("保密", "外传", "不能说")):
                        score += _RERANK_WITCH_SECRET_BONUS
                    elif "魔女" in combined_text and "保密" not in combined_text:
                        score -= _RERANK_WITCH_NO_SECRET_PENALTY

            # ---- club/divination ----
            if "club" in query_tags or "divination" in query_tags:
                if not any(token in combined_text for token in CLUB_HINTS):
                    score -= _RERANK_NO_CLUB_HINT_PENALTY

            # ---- gratitude ----
            if "gratitude" in query_tags and "gratitude" not in result_query_tags:
                if not any(token in response_text for token in GRATITUDE_HINTS):
                    score -= _RERANK_NO_GRATITUDE_HINT_PENALTY

            # ---- greeting ----
            if "greeting" in query_tags and "greeting" not in result_query_tags:
                if not any(token in response_text for token in GREETING_HINTS):
                    score -= _RERANK_NO_GREETING_HINT_PENALTY

            # ---- noise result ----
            if normalized_result_query in {"……", "……（咽口水）……", "………………"}:
                score -= _RERANK_NOISE_RESULT_PENALTY

            # ---- post-filter positive bonuses ----
            if "comfort" in query_tags and any(
                token in response_text for token in SUPPORTIVE_HINTS
            ):
                score += _RERANK_COMFORT_BONUS
            if "greeting" in query_tags and any(token in response_text for token in GREETING_HINTS):
                score += _RERANK_GREETING_BONUS
            if "gratitude" in query_tags and any(
                token in response_text for token in GRATITUDE_HINTS
            ):
                score += _RERANK_GRATITUDE_BONUS
            if "relationship" in query_tags and any(
                token in response_text for token in ROMANCE_HINTS
            ):
                score += _RERANK_RELATIONSHIP_BONUS
            if "witch" in query_tags and any(token in combined_text for token in WITCH_HINTS):
                score += _RERANK_WITCH_BONUS
            if ("club" in query_tags or "divination" in query_tags) and any(
                token in combined_text for token in CLUB_HINTS
            ):
                score += _RERANK_CLUB_BONUS

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

    def retrieve_and_filter(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
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
            final_results = self._rerank_contexts(query, filtered)[:top_k]
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
        context_results: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
        response_language: str = "zh",
    ) -> list[dict[str, str]]:
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

        system_sections = [_CHARACTER_CARD]
        if _PERSONA_REFERENCE_BLOCK:
            system_sections.append(_PERSONA_REFERENCE_BLOCK)
        system_sections.append(language_block)
        system_sections.append(rag_block)
        system_content = "\n\n".join(system_sections)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
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
        history: list[dict[str, str]] | None = None,
        response_language: str = "zh",
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """Returns (messages_for_llm, filtered_contexts)."""
        contexts = self.retrieve_and_filter(query, top_k)
        messages = self.build_messages(
            query,
            contexts,
            history,
            response_language=response_language,
        )
        return messages, contexts
