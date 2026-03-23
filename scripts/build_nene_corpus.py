"""Build curated Nene datasets from extracted route data and the legacy train set.

This script does not overwrite the live dataset in `data/raw/train.jsonl`.
Instead, it creates reviewable outputs under `data/processed/`:

    - nene_core_safe.jsonl: clean route pairs from common + Nene routes
    - nene_extended_safe.jsonl: all clean extracted pairs
    - nene_review.jsonl: extracted pairs that require manual review
    - nene_legacy_clean.jsonl: legacy train samples that survived cleanup
    - nene_merged_train.jsonl: ready-to-promote dataset matching train.jsonl
    - nene_merge_report.json: counts and filtering statistics
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_TRAIN_PATH = PROJECT_ROOT / "data" / "raw" / "train.jsonl"
RAW_SAFE_PATH = PROJECT_ROOT / "data" / "raw" / "nene_ks_safe.jsonl"
RAW_REVIEW_PATH = PROJECT_ROOT / "data" / "raw" / "nene_ks_review.jsonl"
BACKUP_DATASET_DIR = PROJECT_ROOT / "data" / "backups" / "datasets"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

CORE_SAFE_NAME = "nene_core_safe.jsonl"
EXTENDED_SAFE_NAME = "nene_extended_safe.jsonl"
REVIEW_NAME = "nene_review.jsonl"
LEGACY_CLEAN_NAME = "nene_legacy_clean.jsonl"
MERGED_TRAIN_NAME = "nene_merged_train.jsonl"
REPORT_NAME = "nene_merge_report.json"

SYSTEM_PROMPT = (
    "你现在扮演《魔女的夜宴》中的绫地宁宁。请始终使用中文，以宁宁本人的口吻与"
    "保科君自然对话。宁宁是姬松学园二年级生，也是超自然研究部部长，不是瀬名学"
    "园的学生，也不是图书委员。你温柔、认真、体贴，面对保科君时偶尔会害羞和迟"
    "疑，但整体要保持克制、礼貌、可信。请模仿宁宁的语气与关系感，不要跳出角色，"
    "不要直接照搬样本原句，也不要主动暴露自己作为魔女的秘密身份，除非对话上下"
    "文已经明确谈到这一设定。如果样本细节与角色设定冲突，以角色设定为准。"
)

EXPLICIT_HINTS = (
    "初体験",
    "Ｈ",
    "H的",
    "えっち",
    "セックス",
    "裸",
    "下着",
    "自慰",
    "肉棒",
    "高潮",
    "小●穴",
    "阴茎",
    "乳头",
    "湿了",
    "射了",
    "射出来",
    "射精",
    "做愛",
    "做爱",
    "性爱",
    "色情",
    "裸体",
    "乳房",
    "亲热",
    "呻吟",
)
ANNOTATION_HINTS = ("译注",)
NOISE_RE = re.compile(r"[ \t\r\n\u3000…。，、！？!?～~\-—（）()「」『』【】,.，、:：;；]")
MOAN_RE = re.compile(r"(?:[哈啊嗯呜噗呼呀唔]{2,}[，、…！]*){3,}")


def count_nonempty_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def resolve_default_legacy_train_path() -> Path:
    if BACKUP_DATASET_DIR.exists():
        candidates = list(BACKUP_DATASET_DIR.glob("train.*.jsonl"))
        if candidates:
            return min(candidates, key=lambda path: (count_nonempty_lines(path), path.name))
    return RAW_TRAIN_PATH


DEFAULT_LEGACY_TRAIN_PATH = resolve_default_legacy_train_path()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def extract_dialogue_pair(item: dict[str, Any]) -> tuple[str, str]:
    user_text = ""
    assistant_text = ""
    for message in item.get("messages", []):
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if role == "user" and not user_text:
            user_text = content
        elif role == "assistant" and not assistant_text:
            assistant_text = content
    return user_text, assistant_text


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pair_key(user_text: str, assistant_text: str) -> tuple[str, str]:
    return normalize_text(user_text), normalize_text(assistant_text)


def is_core_source(source_name: str) -> bool:
    return "共通" in source_name or "寧々" in source_name


def split_safe_records(
    safe_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    core_records: list[dict[str, Any]] = []
    extended_records: list[dict[str, Any]] = []

    for record in safe_records:
        extended_records.append(record)
        metadata = record.get("metadata", {})
        sources = metadata.get("sources", [])
        if any(isinstance(source, str) and is_core_source(source) for source in sources):
            core_records.append(record)

    return core_records, extended_records


def is_low_signal_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True

    condensed = NOISE_RE.sub("", normalized)
    if not condensed:
        return True

    if all(char in "哈啊嗯呜噗呼呀唔诶欸哇" for char in condensed):
        return True

    return False


def has_unmatched_quote(text: str) -> bool:
    return (
        text.count("「") != text.count("」")
        or text.count("『") != text.count("』")
        or (text.endswith(("」", "』")) and not text.startswith(("「", "『")))
    )


def classify_pair(user_text: str, assistant_text: str) -> set[str]:
    reasons: set[str] = set()
    if not user_text or not assistant_text:
        reasons.add("empty")

    haystack = "\n".join((user_text, assistant_text))

    if any(keyword in haystack for keyword in ANNOTATION_HINTS):
        reasons.add("annotation")

    if (
        any(keyword in haystack for keyword in EXPLICIT_HINTS)
        or "●" in haystack
        or MOAN_RE.search(haystack)
    ):
        reasons.add("sensitive")

    if is_low_signal_text(assistant_text):
        reasons.add("low_signal")

    if has_unmatched_quote(user_text) or has_unmatched_quote(assistant_text):
        reasons.add("malformed")

    return reasons


def attach_review_reasons(record: dict[str, Any], reasons: set[str]) -> dict[str, Any]:
    updated = deepcopy(record)
    metadata = updated.setdefault("metadata", {})
    metadata["review_reasons"] = sorted(reasons)
    return updated


def filter_extracted_safe_records(
    safe_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    accepted: list[dict[str, Any]] = []
    diverted_to_review: list[dict[str, Any]] = []

    for record in safe_records:
        stats["extracted_total"] += 1
        user_text, assistant_text = extract_dialogue_pair(record)
        reasons = classify_pair(user_text, assistant_text)

        if reasons:
            for reason in sorted(reasons):
                stats[f"extracted_filtered_{reason}"] += 1
            diverted_to_review.append(attach_review_reasons(record, reasons))
            continue

        accepted.append(record)
        stats["extracted_kept"] += 1

    return accepted, diverted_to_review, stats


def build_training_record(user_text: str, assistant_text: str) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    }


def build_legacy_clean_records(
    legacy_records: list[dict[str, Any]],
    existing_keys: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    cleaned: list[dict[str, Any]] = []
    seen_keys = set(existing_keys)

    for record in legacy_records:
        stats["legacy_total"] += 1
        user_text, assistant_text = extract_dialogue_pair(record)
        reasons = classify_pair(user_text, assistant_text)

        if reasons:
            for reason in sorted(reasons):
                stats[f"legacy_filtered_{reason}"] += 1
            continue

        key = pair_key(user_text, assistant_text)
        if key in seen_keys:
            stats["legacy_filtered_duplicate"] += 1
            continue

        seen_keys.add(key)
        cleaned.append(build_training_record(user_text, assistant_text))
        stats["legacy_kept"] += 1

    return cleaned, stats


def build_report(
    *,
    safe_path: Path,
    review_path: Path,
    legacy_path: Path,
    output_dir: Path,
    extracted_stats: Counter[str],
    core_safe_records: list[dict[str, Any]],
    extended_safe_records: list[dict[str, Any]],
    review_records: list[dict[str, Any]],
    legacy_stats: Counter[str],
    merged_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "legacy_path": str(legacy_path),
        "raw_safe_path": str(safe_path),
        "raw_review_path": str(review_path),
        "output_dir": str(output_dir),
        "system_prompt": SYSTEM_PROMPT,
        "extracted_total": extracted_stats["extracted_total"],
        "extracted_kept": extracted_stats["extracted_kept"],
        "extracted_filtered_annotation": extracted_stats["extracted_filtered_annotation"],
        "extracted_filtered_empty": extracted_stats["extracted_filtered_empty"],
        "extracted_filtered_low_signal": extracted_stats["extracted_filtered_low_signal"],
        "extracted_filtered_malformed": extracted_stats["extracted_filtered_malformed"],
        "extracted_filtered_sensitive": extracted_stats["extracted_filtered_sensitive"],
        "core_safe_count": len(core_safe_records),
        "extended_safe_count": len(extended_safe_records),
        "review_count": len(review_records),
        "legacy_total": legacy_stats["legacy_total"],
        "legacy_filtered_annotation": legacy_stats["legacy_filtered_annotation"],
        "legacy_kept": legacy_stats["legacy_kept"],
        "legacy_filtered_duplicate": legacy_stats["legacy_filtered_duplicate"],
        "legacy_filtered_empty": legacy_stats["legacy_filtered_empty"],
        "legacy_filtered_low_signal": legacy_stats["legacy_filtered_low_signal"],
        "legacy_filtered_malformed": legacy_stats["legacy_filtered_malformed"],
        "legacy_filtered_sensitive": legacy_stats["legacy_filtered_sensitive"],
        "merged_train_count": len(merged_records),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a curated Nene training corpus.")
    parser.add_argument("--safe-path", default=str(RAW_SAFE_PATH))
    parser.add_argument("--review-path", default=str(RAW_REVIEW_PATH))
    parser.add_argument("--legacy-path", default=str(DEFAULT_LEGACY_TRAIN_PATH))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    safe_path = Path(args.safe_path)
    review_path = Path(args.review_path)
    legacy_path = Path(args.legacy_path)
    output_dir = Path(args.output_dir)

    safe_records = load_jsonl(safe_path)
    review_records = load_jsonl(review_path)
    legacy_records = load_jsonl(legacy_path)

    (
        filtered_safe_records,
        additional_review_records,
        extracted_stats,
    ) = filter_extracted_safe_records(safe_records)
    combined_review_records = review_records + additional_review_records

    core_safe_records, extended_safe_records = split_safe_records(filtered_safe_records)
    core_train_records = [
        build_training_record(*extract_dialogue_pair(record)) for record in core_safe_records
    ]
    core_keys = {pair_key(*extract_dialogue_pair(record)) for record in core_safe_records}

    legacy_clean_records, legacy_stats = build_legacy_clean_records(legacy_records, core_keys)
    merged_records = core_train_records + legacy_clean_records

    write_jsonl(core_safe_records, output_dir / CORE_SAFE_NAME)
    write_jsonl(extended_safe_records, output_dir / EXTENDED_SAFE_NAME)
    write_jsonl(combined_review_records, output_dir / REVIEW_NAME)
    write_jsonl(legacy_clean_records, output_dir / LEGACY_CLEAN_NAME)
    write_jsonl(merged_records, output_dir / MERGED_TRAIN_NAME)

    report = build_report(
        safe_path=safe_path,
        review_path=review_path,
        legacy_path=legacy_path,
        output_dir=output_dir,
        extracted_stats=extracted_stats,
        core_safe_records=core_safe_records,
        extended_safe_records=extended_safe_records,
        review_records=combined_review_records,
        legacy_stats=legacy_stats,
        merged_records=merged_records,
    )
    (output_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
