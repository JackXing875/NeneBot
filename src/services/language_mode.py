"""Heuristics for deciding the reply language for a chat turn."""

from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_LANGUAGES = {"zh", "en", "ja"}
PUNCTUATION_SPACE_RE = re.compile(r"[\s\.,!?~:;，。！？、：；\-_/\\]+")

ENGLISH_GREETING_RE = re.compile(
    r"^\s*(?:hi|hello|hey|yo|good\s+morning|good\s+afternoon|good\s+evening)[!.?~\s]*$",
    re.IGNORECASE,
)
ENGLISH_TEXT_RE = re.compile(r"[A-Za-z]")
JAPANESE_SCRIPT_RE = re.compile(r"[\u3040-\u30ff]")
CHINESE_SWITCH_PATTERNS: dict[str, tuple[str, ...]] = {
    "zh": (
        "请用中文",
        "用中文回复",
        "用中文回答",
        "说中文",
        "中文就行",
        "中文",
        "汉语",
        "普通话",
    ),
    "en": (
        "请用英文",
        "请用英语",
        "用英文回复",
        "用英语回答",
        "说英文",
        "说英语",
        "英文",
        "英语",
    ),
    "ja": (
        "请用日语",
        "用日语回复",
        "用日语回答",
        "说日语",
        "日本语",
        "日语",
        "日文",
        "日语吧",
    ),
}
ENGLISH_SWITCH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "zh": (
        re.compile(r"\b(?:reply|respond|speak|use)\s+in\s+chinese\b", re.IGNORECASE),
        re.compile(r"\buse\s+chinese\b", re.IGNORECASE),
        re.compile(r"\bchinese\s+please\b", re.IGNORECASE),
        re.compile(r"\bspeak\s+chinese\b", re.IGNORECASE),
    ),
    "en": (
        re.compile(r"\b(?:reply|respond|speak|use)\s+in\s+english\b", re.IGNORECASE),
        re.compile(r"\buse\s+english\b", re.IGNORECASE),
        re.compile(r"\bplease\s+use\s+english\b", re.IGNORECASE),
        re.compile(r"\benglish\s+please\b", re.IGNORECASE),
        re.compile(r"\bspeak\s+english\b", re.IGNORECASE),
        re.compile(r"\bcan\s+you\s+use\s+english\b", re.IGNORECASE),
    ),
    "ja": (
        re.compile(r"\b(?:reply|respond|speak|use)\s+in\s+japanese\b", re.IGNORECASE),
        re.compile(r"\buse\s+japanese\b", re.IGNORECASE),
        re.compile(r"\bjapanese\s+please\b", re.IGNORECASE),
        re.compile(r"\bspeak\s+japanese\b", re.IGNORECASE),
    ),
}
JAPANESE_SWITCH_PATTERNS: dict[str, tuple[str, ...]] = {
    "zh": ("中国語で", "中国語", "中文で"),
    "en": ("英語で", "英語"),
    "ja": ("日本語で", "日本語"),
}
DIRECT_LANGUAGE_ALIASES = {
    "zh": {
        "中文",
        "汉语",
        "普通话",
        "chinese",
        "usechinese",
        "speakchinese",
        "replyinchinese",
    },
    "en": {
        "英文",
        "英语",
        "english",
        "useenglish",
        "speakenglish",
        "replyinenglish",
    },
    "ja": {
        "日语",
        "日文",
        "日本语",
        "日本語",
        "japanese",
        "usejapanese",
        "speakjapanese",
        "replyinjapanese",
    },
}


@dataclass(frozen=True)
class LanguageDecision:
    """Reply-language choice for one chat turn."""

    response_language: str
    persist_language: str | None = None


def normalize_switch_text(query: str) -> str:
    """Normalize user text for short explicit language-switch commands."""
    normalized = query.strip().lower()
    return PUNCTUATION_SPACE_RE.sub("", normalized)


def detect_explicit_language_switch(query: str) -> str | None:
    """Return an explicitly requested language switch from the user query."""
    normalized = query.strip()
    if not normalized:
        return None
    compact = normalize_switch_text(normalized)

    for language, aliases in DIRECT_LANGUAGE_ALIASES.items():
        if compact in aliases:
            return language

    for language, patterns in CHINESE_SWITCH_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            return language

    for language, patterns in JAPANESE_SWITCH_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            return language

    for language, patterns in ENGLISH_SWITCH_PATTERNS.items():
        if any(pattern.search(normalized) for pattern in patterns):
            return language

    return None


def is_simple_english_greeting(query: str) -> bool:
    """Return whether the user only sent a very short English greeting."""
    return bool(ENGLISH_GREETING_RE.fullmatch(query.strip()))


def looks_like_substantive_english(query: str) -> bool:
    """Return whether the query is mostly meaningful English text."""
    normalized = query.strip()
    if not normalized or is_simple_english_greeting(normalized):
        return False
    if JAPANESE_SCRIPT_RE.search(normalized):
        return False
    words = re.findall(r"[A-Za-z]+", normalized)
    return len(words) >= 3 and bool(ENGLISH_TEXT_RE.search(normalized))


def resolve_reply_language(
    query: str,
    *,
    stored_preference: str | None = None,
) -> LanguageDecision:
    """Resolve the reply language for the current turn."""
    explicit = detect_explicit_language_switch(query)
    if explicit in SUPPORTED_LANGUAGES:
        return LanguageDecision(response_language=explicit, persist_language=explicit)

    if stored_preference in SUPPORTED_LANGUAGES:
        return LanguageDecision(response_language=stored_preference)

    if is_simple_english_greeting(query):
        return LanguageDecision(response_language="zh")

    if JAPANESE_SCRIPT_RE.search(query):
        return LanguageDecision(response_language="ja")

    if looks_like_substantive_english(query):
        return LanguageDecision(response_language="en")

    return LanguageDecision(response_language="zh")
