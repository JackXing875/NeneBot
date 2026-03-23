from scripts.build_nene_corpus import (
    SYSTEM_PROMPT,
    build_legacy_clean_records,
    build_training_record,
    classify_pair,
    filter_extracted_safe_records,
    split_safe_records,
)


def test_split_safe_records_prefers_common_and_nene_routes() -> None:
    safe_records = [
        {
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "早上好"},
            ],
            "metadata": {"sources": ["012.共通－魔女.ks.txt"]},
        },
        {
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "晚上好"},
            ],
            "metadata": {"sources": ["201.めぐる－记念撮影.ks.txt"]},
        },
    ]

    core_records, extended_records = split_safe_records(safe_records)

    assert len(core_records) == 1
    assert len(extended_records) == 2
    assert core_records[0]["metadata"]["sources"] == ["012.共通－魔女.ks.txt"]


def test_classify_pair_rejects_sensitive_noise_annotations_and_malformed_text() -> None:
    assert "sensitive" in classify_pair("……", "嗯，呼……哈，哈，啊，啊啊啊啊……呼啊啊啊……")
    assert "low_signal" in classify_pair("……", "………")
    assert "malformed" in classify_pair("你好", "白蛇占再怎么说也做不到啦」")
    assert "annotation" in classify_pair("你好", "这是译注：解释文本")
    assert "sensitive" in classify_pair("你喜欢我的肉棒吗", "……")


def test_filter_extracted_safe_records_diverts_flagged_pairs_to_review() -> None:
    safe_records = [
        {
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "早上好"},
            ],
            "metadata": {"sources": ["012.共通－魔女.ks.txt"]},
        },
        {
            "messages": [
                {"role": "user", "content": "啊，学姐！（译注：说明）"},
                {"role": "assistant", "content": "早上好"},
            ],
            "metadata": {"sources": ["012.共通－魔女.ks.txt"]},
        },
    ]

    accepted, review_records, stats = filter_extracted_safe_records(safe_records)

    assert len(accepted) == 1
    assert len(review_records) == 1
    assert review_records[0]["metadata"]["review_reasons"] == ["annotation"]
    assert stats["extracted_filtered_annotation"] == 1


def test_build_legacy_clean_records_dedupes_against_core_pairs() -> None:
    legacy_records = [
        {
            "messages": [
                {"role": "system", "content": "old"},
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "早上好"},
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "old"},
                {"role": "user", "content": "你辛苦了"},
                {"role": "assistant", "content": "一点都不辛苦"},
            ]
        },
    ]

    cleaned, stats = build_legacy_clean_records(
        legacy_records=legacy_records,
        existing_keys={("你好", "早上好")},
    )

    assert len(cleaned) == 1
    assert cleaned[0] == build_training_record("你辛苦了", "一点都不辛苦")
    assert cleaned[0]["messages"][0]["content"] == SYSTEM_PROMPT
    assert stats["legacy_filtered_duplicate"] == 1
