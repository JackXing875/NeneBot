import json
from pathlib import Path

from scripts.promote_dataset import promote_dataset, validate_dataset_file


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_validate_dataset_file_requires_user_and_assistant(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    write_jsonl(
        path,
        [
            {
                "messages": [
                    {"role": "user", "content": "你好"},
                ]
            }
        ],
    )

    try:
        validate_dataset_file(path)
    except ValueError as exc:
        assert "must contain both user and assistant content" in str(exc)
    else:
        raise AssertionError("Expected validate_dataset_file to reject incomplete records")


def test_promote_dataset_dry_run_does_not_modify_destination(tmp_path: Path) -> None:
    source = tmp_path / "processed" / "merged.jsonl"
    destination = tmp_path / "raw" / "train.jsonl"
    backup_dir = tmp_path / "backups"

    write_jsonl(
        source,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "新数据"},
                    {"role": "assistant", "content": "新回复"},
                ]
            }
        ],
    )
    write_jsonl(
        destination,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "旧数据"},
                    {"role": "assistant", "content": "旧回复"},
                ]
            }
        ],
    )

    result = promote_dataset(
        source=source,
        destination=destination,
        backup_dir=backup_dir,
        dry_run=True,
        rebuild=False,
    )

    assert result["dry_run"] is True
    assert result["backup_path"] is None
    assert "旧数据" in destination.read_text(encoding="utf-8")


def test_promote_dataset_creates_backup_and_copies_source(tmp_path: Path) -> None:
    source = tmp_path / "processed" / "merged.jsonl"
    destination = tmp_path / "raw" / "train.jsonl"
    backup_dir = tmp_path / "backups"

    write_jsonl(
        source,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "新数据"},
                    {"role": "assistant", "content": "新回复"},
                ]
            }
        ],
    )
    write_jsonl(
        destination,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "旧数据"},
                    {"role": "assistant", "content": "旧回复"},
                ]
            }
        ],
    )

    result = promote_dataset(
        source=source,
        destination=destination,
        backup_dir=backup_dir,
        dry_run=False,
        rebuild=False,
    )

    assert result["backup_path"] is not None
    assert "新数据" in destination.read_text(encoding="utf-8")
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert "旧数据" in backup_path.read_text(encoding="utf-8")


def test_promote_dataset_rolls_back_destination_when_rebuild_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "processed" / "merged.jsonl"
    destination = tmp_path / "raw" / "train.jsonl"
    backup_dir = tmp_path / "backups"

    write_jsonl(
        source,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "新数据"},
                    {"role": "assistant", "content": "新回复"},
                ]
            }
        ],
    )
    write_jsonl(
        destination,
        [
            {
                "messages": [
                    {"role": "system", "content": "x"},
                    {"role": "user", "content": "旧数据"},
                    {"role": "assistant", "content": "旧回复"},
                ]
            }
        ],
    )

    monkeypatch.setattr(
        "scripts.init_vector_db.main",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    try:
        promote_dataset(
            source=source,
            destination=destination,
            backup_dir=backup_dir,
            dry_run=False,
            rebuild=True,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected rebuild failure to bubble up")

    assert "旧数据" in destination.read_text(encoding="utf-8")
