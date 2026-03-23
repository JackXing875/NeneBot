"""Promote a reviewed dataset into the live training path with backup and rebuild.

Typical usage:

    python scripts/promote_dataset.py

This promotes `data/processed/nene_merged_train.jsonl` to `data/raw/train.jsonl`,
creates a timestamped backup of the previous live dataset, and rebuilds the FAISS
index unless `--no-rebuild` is passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SOURCE_PATH = PROJECT_ROOT / "data" / "processed" / "nene_merged_train.jsonl"
DEFAULT_DEST_PATH = PROJECT_ROOT / "data" / "raw" / "train.jsonl"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups" / "datasets"


def validate_dataset_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    line_count = 0
    preview: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {idx} in {path}.") from exc

            if not isinstance(payload, dict):
                raise ValueError(f"Line {idx} in {path} must be a JSON object.")

            messages = payload.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"Line {idx} in {path} must include a non-empty messages list.")

            user_text = ""
            assistant_text = ""
            for message in messages:
                if not isinstance(message, dict):
                    raise ValueError(f"Line {idx} in {path} contains a non-object message entry.")
                role = message.get("role")
                content = str(message.get("content", "")).strip()
                if role == "user" and not user_text:
                    user_text = content
                elif role == "assistant" and not assistant_text:
                    assistant_text = content

            if not user_text or not assistant_text:
                raise ValueError(
                    f"Line {idx} in {path} must contain both user and assistant content."
                )

            line_count += 1
            if len(preview) < 3:
                preview.append({"user": user_text, "assistant": assistant_text})

    if line_count == 0:
        raise ValueError(f"Dataset file is empty: {path}")

    return {
        "path": str(path),
        "line_count": line_count,
        "size_bytes": path.stat().st_size,
        "preview": preview,
    }


def backup_existing_dataset(destination: Path, backup_dir: Path) -> Path | None:
    if not destination.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{destination.stem}.{timestamp}{destination.suffix}"
    shutil.copy2(destination, backup_path)
    return backup_path


def promote_dataset(
    source: Path,
    destination: Path,
    backup_dir: Path,
    *,
    dry_run: bool = False,
    rebuild: bool = True,
) -> dict[str, Any]:
    source_summary = validate_dataset_file(source)
    destination_summary = (
        validate_dataset_file(destination)
        if destination.exists()
        else {"path": str(destination), "line_count": 0, "size_bytes": 0, "preview": []}
    )

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "source": source_summary,
        "destination_before": destination_summary,
        "backup_path": None,
        "destination_after": source_summary if dry_run else None,
        "rebuild_triggered": False,
    }

    if dry_run:
        return result

    backup_path = backup_existing_dataset(destination, backup_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    result["backup_path"] = str(backup_path) if backup_path else None
    try:
        result["destination_after"] = validate_dataset_file(destination)

        if rebuild:
            try:
                from scripts.init_vector_db import main as rebuild_index  # type: ignore[import]
            except ModuleNotFoundError:
                from init_vector_db import main as rebuild_index  # type: ignore[import]

            rebuild_index()
            result["rebuild_triggered"] = True
    except Exception:
        if backup_path is not None and backup_path.exists():
            shutil.copy2(backup_path, destination)
        raise

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote a reviewed JSONL dataset into the live train.jsonl path."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE_PATH),
        help="Reviewed dataset to promote.",
    )
    parser.add_argument(
        "--destination",
        default=str(DEFAULT_DEST_PATH),
        help="Live dataset path used by the application.",
    )
    parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory for timestamped backups.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and summarize only; do not write or rebuild.",
    )
    parser.add_argument(
        "--no-rebuild",
        action="store_true",
        help="Skip vector-store rebuild after promotion.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = promote_dataset(
        source=Path(args.source),
        destination=Path(args.destination),
        backup_dir=Path(args.backup_dir),
        dry_run=bool(args.dry_run),
        rebuild=not bool(args.no_rebuild),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
