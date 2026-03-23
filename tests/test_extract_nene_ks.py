from pathlib import Path

from scripts.extract_nene_ks import (
    dedupe_pairs,
    extract_pairs_from_turns,
    parse_dialogue_turns,
)


def test_parse_dialogue_turns_reads_bilingual_ks_blocks(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.ks.txt"
    file_path.write_text(
        "\n".join(
            [
                "[0x00000000]柊史",
                ";[0x00000000]柊史",
                "[0x00000001]「おはよう」",
                ";[0x00000001]「早上好」",
                "[0x00000002]寧々",
                ";[0x00000002]宁宁",
                "[0x00000003]「おはようございます、保科君」",
                ";[0x00000003]「早上好，保科君」",
            ]
        ),
        encoding="utf-8",
    )

    turns = parse_dialogue_turns(file_path)

    assert len(turns) == 2
    assert turns[0].speaker_jp == "柊史"
    assert turns[0].zh_text == "早上好"
    assert turns[1].speaker_jp == "寧々"
    assert turns[1].zh_text == "早上好，保科君"


def test_extract_pairs_from_turns_keeps_previous_non_nene_turn(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.ks.txt"
    file_path.write_text(
        "\n".join(
            [
                "[0x00000000]柊史",
                ";[0x00000000]柊史",
                "[0x00000001]「ありがとう」",
                ";[0x00000001]「谢谢」",
                "[0x00000002]寧々",
                ";[0x00000002]宁宁",
                "[0x00000003]「どういたしまして」",
                ";[0x00000003]「不客气」",
            ]
        ),
        encoding="utf-8",
    )

    pairs = extract_pairs_from_turns(parse_dialogue_turns(file_path))

    assert len(pairs) == 1
    assert pairs[0].user_zh == "谢谢"
    assert pairs[0].assistant_zh == "不客气"


def test_dedupe_pairs_merges_duplicate_sources(tmp_path: Path) -> None:
    file_a = tmp_path / "a.ks.txt"
    file_b = tmp_path / "b.ks.txt"
    content = "\n".join(
        [
            "[0x00000000]柊史",
            ";[0x00000000]柊史",
            "[0x00000001]「ありがとう」",
            ";[0x00000001]「谢谢」",
            "[0x00000002]寧々",
            ";[0x00000002]宁宁",
            "[0x00000003]「どういたしまして」",
            ";[0x00000003]「不客气」",
        ]
    )
    file_a.write_text(content, encoding="utf-8")
    file_b.write_text(content, encoding="utf-8")

    pairs = extract_pairs_from_turns(parse_dialogue_turns(file_a)) + extract_pairs_from_turns(
        parse_dialogue_turns(file_b)
    )
    deduped = dedupe_pairs(pairs)

    assert len(deduped) == 1
    assert deduped[0].source_files == {"a.ks.txt", "b.ks.txt"}
