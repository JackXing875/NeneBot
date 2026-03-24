from src.services.language_mode import resolve_reply_language


def test_explicit_language_switch_persists_english_preference() -> None:
    decision = resolve_reply_language("please use English")

    assert decision.response_language == "en"
    assert decision.persist_language == "en"


def test_short_english_switch_command_is_supported() -> None:
    decision = resolve_reply_language("use English")

    assert decision.response_language == "en"
    assert decision.persist_language == "en"


def test_language_aliases_have_tolerant_matching() -> None:
    assert resolve_reply_language("english please").response_language == "en"
    assert resolve_reply_language("中文").response_language == "zh"
    assert resolve_reply_language("日语").response_language == "ja"


def test_japanese_query_uses_japanese_without_persisting() -> None:
    decision = resolve_reply_language("今日は少し疲れました")

    assert decision.response_language == "ja"
    assert decision.persist_language is None


def test_simple_english_greeting_stays_chinese_by_default() -> None:
    decision = resolve_reply_language("hello")

    assert decision.response_language == "zh"


def test_stored_preference_is_reused_when_query_is_ambiguous() -> None:
    decision = resolve_reply_language("谢谢", stored_preference="en")

    assert decision.response_language == "en"
