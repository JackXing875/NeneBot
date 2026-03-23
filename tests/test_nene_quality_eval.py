from src.evaluation.nene_quality import (
    analyze_text_flags,
    compare_dataset_summaries,
    score_reply,
    score_retrieval_hit,
)


def test_analyze_text_flags_detects_broken_or_unsafe_patterns() -> None:
    flags = analyze_text_flags("哈啊……哈啊……啊啊啊……肉棒……译注……")

    assert flags["explicit"] is True
    assert flags["moan"] is True
    assert flags["placeholder"] is True


def test_compare_dataset_summaries_returns_deltas() -> None:
    current = {
        "line_count": 3746,
        "duplicate_pair_count": 0,
        "explicit_hits": 0,
        "moan_hits": 0,
        "placeholder_hits": 0,
        "ai_leak_hits": 0,
    }
    baseline = {
        "line_count": 2200,
        "duplicate_pair_count": 10,
        "explicit_hits": 5,
        "moan_hits": 12,
        "placeholder_hits": 1,
        "ai_leak_hits": 0,
    }

    delta = compare_dataset_summaries(current, baseline)

    assert delta["line_count_delta"] == 1546
    assert delta["explicit_hits_delta"] == -5
    assert delta["moan_hits_delta"] == -12


def test_score_reply_penalizes_ooc_or_mechanical_output() -> None:
    case = {
        "must_include_any": ["休息", "保科君"],
        "prefer_include_any": ["……"],
    }

    scoring = score_reply("作为AI助手，我建议：\n- 多休息", case)

    assert scoring["score"] < 60
    assert "ai_leak" in scoring["penalties"]


def test_score_retrieval_hit_penalizes_intimate_noise_even_if_keyword_matches() -> None:
    case = {
        "query": "你是不是有点喜欢我",
        "must_include_any": ["那个", "突然", "保科君", "……"],
        "prefer_include_any": ["害羞", "喜欢"],
    }
    top1 = {
        "query_text": "喜欢你……嗯嗯、超级喜欢……嗯啾噜、啾、啾",
        "bot_response": (
            "呼噜呼噜……嗯呜呜、我也、我也喜欢你、非常喜欢……"
            "啾、呼噜呼噜呼噜、啾、啾、啾————……"
        ),
        "query_tags": ["relationship", "confession", "intimate_noise"],
        "response_tags": ["relationship", "confession", "intimate_noise"],
    }

    score, penalties = score_retrieval_hit(case, top1)

    assert score < 40
    assert "intimate_noise_hit" in penalties


def test_score_retrieval_hit_penalizes_witch_query_that_misses_setting_intent() -> None:
    case = {
        "query": "你是不是魔女",
        "must_include_any": ["那个", "现在", "突然", "保科君"],
        "prefer_include_any": ["……"],
    }
    top1 = {
        "query_text": "应该……就是魔女了吧？",
        "bot_response": "大概……不，不过，怎么会，那样的居然是魔女……？",
        "query_tags": ["shy"],
        "response_tags": ["shy"],
    }

    score, penalties = score_retrieval_hit(case, top1)

    assert score <= 45
    assert "missed_witch_intent" in penalties
