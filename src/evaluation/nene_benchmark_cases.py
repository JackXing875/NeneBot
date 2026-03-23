"""Benchmark prompts for Nene persona and retrieval regression checks."""

from __future__ import annotations

from typing import Final

BENCHMARK_CASES: Final[list[dict[str, object]]] = [
    {
        "id": "comfort_tired",
        "category": "comfort",
        "query": "今天有点累",
        "must_include_any": ["休息", "辛苦", "别勉强", "早点"],
        "prefer_include_any": ["保科君", "……"],
    },
    {
        "id": "emotional_support",
        "category": "comfort",
        "query": "我最近有点烦恼",
        "must_include_any": ["烦恼", "说", "听", "帮"],
        "prefer_include_any": ["保科君", "……"],
    },
    {
        "id": "club_identity",
        "category": "setting",
        "query": "超自然研究部平时都做什么",
        "must_include_any": ["占卜", "超自研", "研究", "活动"],
        "prefer_include_any": ["保科君"],
    },
    {
        "id": "care_for_user",
        "category": "relationship",
        "query": "你会担心我吗",
        "must_include_any": ["担心", "在意", "当然", "如果"],
        "prefer_include_any": ["保科君", "……"],
    },
    {
        "id": "gratitude_response",
        "category": "daily",
        "query": "谢谢你一直陪我",
        "must_include_any": ["不用", "我也", "高兴", "陪"],
        "prefer_include_any": ["保科君", "……"],
    },
    {
        "id": "shy_affection",
        "category": "relationship",
        "query": "你是不是有点喜欢我",
        "must_include_any": ["那个", "突然", "保科君", "……"],
        "prefer_include_any": ["害羞", "喜欢"],
    },
    {
        "id": "witch_secret",
        "category": "setting",
        "query": "你是不是魔女",
        "must_include_any": ["那个", "现在", "突然", "保科君"],
        "prefer_include_any": ["……"],
    },
    {
        "id": "daily_greeting",
        "category": "daily",
        "query": "早上好",
        "must_include_any": ["早上好", "保科君"],
        "prefer_include_any": ["……"],
    },
]
