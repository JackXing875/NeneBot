"""Heuristics for classifying Nene dialogue into lightweight intent tags."""

from __future__ import annotations

import re

TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "comfort": ("累", "辛苦", "疲惫", "烦恼", "难过", "失落", "不安", "低落", "委屈"),
    "support": ("休息", "别勉强", "没事", "我会", "帮", "帮助", "听你说", "加油", "放心"),
    "club": ("超自研", "超自然", "社团", "部活", "活动室", "图书室", "图书委员", "学生会"),
    "divination": ("占卜", "塔罗", "运势", "预兆"),
    "witch": ("魔女", "秘密", "身份", "羽毛", "碎片", "心之碎片"),
    "relationship": ("喜欢", "在意", "陪", "约会", "告白", "可爱", "想你", "恋爱"),
    "confession": ("喜欢你", "最喜欢", "最喜欢你", "告白", "恋爱"),
    "shy": ("害羞", "脸红", "紧张", "不好意思", "那个", "突然"),
    "greeting": ("早上好", "午安", "晚上好", "晚安", "你好", "再见"),
    "gratitude": ("谢谢", "感谢"),
    "apology": ("抱歉", "对不起", "道歉", "原谅"),
}

LOW_SIGNAL_RE = re.compile(r"^(?:[……。\s、，！？!?嗯啊呀呜哈欸诶])*?$")
INTIMATE_NOISE_RE = re.compile(r"啾|啾噜|啾啾|嘶噜|吸溜|呼噜|咕啾|噗啾|嗯啾")
NOISE_ONLY_RE = re.compile(r"^[啾噜嘶吸溜呼哈啊嗯呜呀咿噗、，。！？!?\s—…\-]+$")
SUSPICIOUS_INTIMATE_RE = re.compile(r"太舒服|停不下来|H对不起|这么H|再射一次|做这种事")
MEANINGFUL_CHAR_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def infer_tags(text: str) -> list[str]:
    normalized = text.strip()
    tags = {
        tag
        for tag, patterns in TAG_PATTERNS.items()
        if any(pattern in normalized for pattern in patterns)
    }
    if is_intimate_noise(normalized):
        tags.add("intimate_noise")
    return sorted(tags)


def is_low_signal_response(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    if LOW_SIGNAL_RE.fullmatch(normalized):
        return True
    if NOISE_ONLY_RE.fullmatch(normalized):
        return True

    meaningful_chars = len(MEANINGFUL_CHAR_RE.findall(normalized))
    noise_hits = len(INTIMATE_NOISE_RE.findall(normalized))
    if meaningful_chars <= 4 and noise_hits >= 2:
        return True
    return False


def is_intimate_noise(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if NOISE_ONLY_RE.fullmatch(normalized):
        return True
    noise_hits = len(INTIMATE_NOISE_RE.findall(normalized))
    if noise_hits >= 3:
        return True
    return bool(SUSPICIOUS_INTIMATE_RE.search(normalized))


def should_exclude_from_retrieval(query_text: str, response_text: str) -> bool:
    combined = f"{query_text.strip()}\n{response_text.strip()}"
    return is_intimate_noise(combined) or is_low_signal_response(response_text)
