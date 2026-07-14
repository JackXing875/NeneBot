"""Safe offline transformations for creating derived Character Pack versions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from src.knowledge.pack import (
    EvaluationSuite,
    PackValidationError,
    ValidatedCharacterPack,
    validate_character_pack,
)


@dataclass(frozen=True)
class SourceRemovalReport:
    """Result of deriving a Pack with selected record sources removed."""

    pack: ValidatedCharacterPack
    excluded_sources: tuple[str, ...]
    removed_record_ids: tuple[str, ...]
    removed_evaluation_case_ids: tuple[str, ...]


def _canonical_json(model: BaseModel) -> str:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _write_pack_file(root: Path, relative_path: str, content: str) -> None:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def derive_pack_without_sources(
    pack_dir: str | Path,
    output_dir: str | Path,
    *,
    version: str,
    excluded_sources: set[str],
) -> SourceRemovalReport:
    """Create a new Pack version excluding exact provenance source values.

    The source Pack is never modified. Evaluation expectations are filtered to
    remaining record ids; cases with no remaining expectation are removed.
    """
    pack = validate_character_pack(pack_dir)
    sources = {source.strip() for source in excluded_sources if source.strip()}
    if not sources:
        raise PackValidationError("At least one non-empty provenance source is required.")

    records = tuple(record for record in pack.records if record.provenance.source not in sources)
    removed_ids = tuple(record.id for record in pack.records if record.provenance.source in sources)
    if not removed_ids:
        raise PackValidationError("No knowledge records matched the requested source values.")
    if not records:
        raise PackValidationError("Source removal would leave the Pack with no knowledge records.")

    remaining_ids = {record.id for record in records}
    evaluation_cases = []
    removed_case_ids: list[str] = []
    for case in pack.evaluation.cases:
        expected_ids = [
            record_id for record_id in case.expected_record_ids if record_id in remaining_ids
        ]
        if not expected_ids:
            removed_case_ids.append(case.id)
            continue
        evaluation_cases.append(case.model_copy(update={"expected_record_ids": expected_ids}))
    if not evaluation_cases:
        raise PackValidationError(
            "Source removal would leave the Pack with no executable evaluation cases."
        )

    output = Path(output_dir).resolve()
    source_root = pack.root.resolve()
    if output == source_root or output.is_relative_to(source_root):
        raise PackValidationError("A derived Pack output must be outside its source Pack.")
    if output.exists():
        raise PackValidationError(f"Derived Pack output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    manifest = pack.manifest.model_copy(update={"version": version})
    evaluation = EvaluationSuite(schema_version=1, cases=evaluation_cases)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        _write_pack_file(stage, "manifest.json", _canonical_json(manifest))
        _write_pack_file(stage, manifest.persona_path, pack.persona)
        _write_pack_file(stage, manifest.prompt_path, pack.prompt)
        _write_pack_file(
            stage,
            manifest.knowledge_path,
            "".join(_canonical_json(record) for record in records),
        )
        _write_pack_file(stage, manifest.evaluation_path, _canonical_json(evaluation))
        _write_pack_file(stage, manifest.theme_path, _canonical_json(pack.theme))
        validate_character_pack(stage)
        os.replace(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)

    derived = validate_character_pack(output)
    return SourceRemovalReport(
        pack=derived,
        excluded_sources=tuple(sorted(sources)),
        removed_record_ids=removed_ids,
        removed_evaluation_case_ids=tuple(removed_case_ids),
    )
