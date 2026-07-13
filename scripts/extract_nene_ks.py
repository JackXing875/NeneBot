"""Extract Nene-related bilingual dialogue pairs from translated `.ks.txt` files.

This parser is tailored to files under `data/raw/jp_routes/`, where each logical
line appears twice:

    [0x00000000]日本語
    ;[0x00000000]中文翻译

The script extracts high-quality dialogue pairs in the form:

    previous non-Nene speaker utterance -> Nene utterance

It also:
    - preserves both Japanese and Chinese text
    - removes exact duplicate pairs while keeping all source files
    - diverts potentially sensitive pairs into a separate review file
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "jp_routes"
DEFAULT_SAFE_OUTPUT = PROJECT_ROOT / "data" / "raw" / "nene_ks_safe.jsonl"
DEFAULT_REVIEW_OUTPUT = PROJECT_ROOT / "data" / "raw" / "nene_ks_review.jsonl"
DEFAULT_REPORT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "nene_ks_report.json"

LINE_RE = re.compile(r"^(?P<comment>;)?\[(?P<idx>0x[0-9A-Fa-f]+)\](?P<text>.*)$")
CONTROL_PREFIX_RE = re.compile(r"^%[^;]+;")
SPEAKER_RE = re.compile(
    r"^[A-Za-z0-9_ぁ-ゟァ-ヴー一-龯々ヶ・ＣＡＢ女子学生保科君柊史寧々宁宁綾地さん]+$"
)

NENE_NAMES_JP = {"寧々"}
NENE_NAMES_ZH = {"宁宁"}
EXPLICIT_HINTS = (
    "初体験",
    "Ｈ",
    "えっち",
    "セックス",
    "裸",
    "下着",
    "胸を",
    "胸に",
    "キス",
    "抱きつく",
    "做愛",
    "做爱",
    "性爱",
    "色情",
    "裸体",
    "乳房",
    "胸部",
    "亲热",
)


@dataclass
class KSLine:
    idx: str
    jp: str = ""
    zh: str = ""
    order: int = 0


@dataclass
class DialogueTurn:
    speaker_jp: str
    speaker_zh: str
    jp_text: str
    zh_text: str
    source_file: str
    idx: str


@dataclass
class ExtractedPair:
    user_jp: str
    user_zh: str
    assistant_jp: str
    assistant_zh: str
    source_files: set[str] = field(default_factory=set)
    source_indices: list[str] = field(default_factory=list)
    sensitive: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "messages": [
                {"role": "user", "content": self.user_zh},
                {"role": "assistant", "content": self.assistant_zh},
            ],
            "metadata": {
                "user_jp": self.user_jp,
                "assistant_jp": self.assistant_jp,
                "user_zh": self.user_zh,
                "assistant_zh": self.assistant_zh,
                "sources": sorted(self.source_files),
                "source_indices": self.source_indices,
                "sensitive": self.sensitive,
            },
        }


def iter_ks_lines(file_path: Path) -> list[KSLine]:
    grouped: dict[str, KSLine] = {}
    ordered_ids: list[str] = []

    for raw in file_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if not match:
            continue

        idx = match.group("idx")
        text = match.group("text").strip()
        if idx not in grouped:
            grouped[idx] = KSLine(idx=idx, order=len(ordered_ids))
            ordered_ids.append(idx)
        if match.group("comment"):
            grouped[idx].zh = text
        else:
            grouped[idx].jp = text

    return [grouped[idx] for idx in ordered_ids]


def normalize_text(text: str) -> str:
    normalized = CONTROL_PREFIX_RE.sub("", text).strip()
    return normalized


def is_dialogue(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized.startswith("「") or normalized.startswith("『")


def is_speaker(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized or is_dialogue(normalized):
        return False
    if any(mark in normalized for mark in ("。", "？", "！", "…", "，", "、", " ", "\n")):
        return False
    return bool(SPEAKER_RE.match(normalized)) and len(normalized) <= 16


def strip_quotes(text: str) -> str:
    normalized = normalize_text(text)
    if normalized.startswith(("「", "『")) and normalized.endswith(("」", "』")):
        return normalized[1:-1].strip()
    return normalized


def parse_dialogue_turns(file_path: Path) -> list[DialogueTurn]:
    current_speaker_jp = ""
    current_speaker_zh = ""
    turns: list[DialogueTurn] = []

    for item in iter_ks_lines(file_path):
        jp = normalize_text(item.jp)
        zh = normalize_text(item.zh)
        if not jp:
            continue

        if is_speaker(jp):
            current_speaker_jp = jp
            current_speaker_zh = zh or current_speaker_zh
            continue

        if is_dialogue(jp) and current_speaker_jp:
            turns.append(
                DialogueTurn(
                    speaker_jp=current_speaker_jp,
                    speaker_zh=current_speaker_zh,
                    jp_text=strip_quotes(jp),
                    zh_text=strip_quotes(zh),
                    source_file=file_path.name,
                    idx=item.idx,
                )
            )

    return turns


def is_nene_turn(turn: DialogueTurn) -> bool:
    return turn.speaker_jp in NENE_NAMES_JP or turn.speaker_zh in NENE_NAMES_ZH


def is_sensitive_pair(user_jp: str, user_zh: str, assistant_jp: str, assistant_zh: str) -> bool:
    haystack = "\n".join((user_jp, user_zh, assistant_jp, assistant_zh))
    return any(keyword in haystack for keyword in EXPLICIT_HINTS)


def extract_pairs_from_turns(turns: list[DialogueTurn]) -> list[ExtractedPair]:
    pairs: list[ExtractedPair] = []
    previous_non_nene: DialogueTurn | None = None

    for turn in turns:
        if is_nene_turn(turn):
            if previous_non_nene is None:
                continue
            pairs.append(
                ExtractedPair(
                    user_jp=previous_non_nene.jp_text,
                    user_zh=previous_non_nene.zh_text,
                    assistant_jp=turn.jp_text,
                    assistant_zh=turn.zh_text,
                    source_files={turn.source_file},
                    source_indices=[turn.idx],
                    sensitive=is_sensitive_pair(
                        previous_non_nene.jp_text,
                        previous_non_nene.zh_text,
                        turn.jp_text,
                        turn.zh_text,
                    ),
                )
            )
        else:
            previous_non_nene = turn

    return pairs


def dedupe_pairs(pairs: list[ExtractedPair]) -> list[ExtractedPair]:
    deduped: dict[tuple[str, str, str, str], ExtractedPair] = {}
    for pair in pairs:
        key = (pair.user_jp, pair.user_zh, pair.assistant_jp, pair.assistant_zh)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = pair
            continue

        existing.source_files.update(pair.source_files)
        existing.source_indices.extend(pair.source_indices)
        existing.sensitive = existing.sensitive or pair.sensitive

    return list(deduped.values())


def write_jsonl(records: list[ExtractedPair], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record.to_json(), ensure_ascii=False) + "\n")


def build_report(
    input_dir: Path,
    all_pairs: list[ExtractedPair],
    safe_pairs: list[ExtractedPair],
    review_pairs: list[ExtractedPair],
) -> dict[str, Any]:
    source_files = sorted(str(path.name) for path in input_dir.glob("*.ks.txt"))
    return {
        "input_dir": str(input_dir),
        "source_file_count": len(source_files),
        "source_files": source_files,
        "total_pairs_before_filter": len(all_pairs),
        "safe_pair_count": len(safe_pairs),
        "review_pair_count": len(review_pairs),
    }


def main() -> None:
    input_dir = DEFAULT_INPUT_DIR
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    all_pairs: list[ExtractedPair] = []
    for file_path in sorted(input_dir.glob("*.ks.txt")):
        turns = parse_dialogue_turns(file_path)
        all_pairs.extend(extract_pairs_from_turns(turns))

    deduped = dedupe_pairs(all_pairs)
    safe_pairs = [pair for pair in deduped if not pair.sensitive]
    review_pairs = [pair for pair in deduped if pair.sensitive]

    write_jsonl(safe_pairs, DEFAULT_SAFE_OUTPUT)
    write_jsonl(review_pairs, DEFAULT_REVIEW_OUTPUT)
    report = build_report(input_dir, deduped, safe_pairs, review_pairs)
    DEFAULT_REPORT_OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
