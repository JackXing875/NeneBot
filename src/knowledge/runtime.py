"""Validated runtime descriptor compiled from a Character Pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.knowledge.artifacts import ArtifactValidationError, PublishedArtifact
from src.knowledge.pack import PackTheme, Provenance, ValidatedCharacterPack, validate_pack_id

RUNTIME_DESCRIPTOR_FILENAME = "runtime.json"
EVALUATION_ARTIFACT_FILENAME = "evaluation.json"


class RuntimeCharacter(BaseModel):
    """All authored character content needed by a read-only chat runtime."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    pack_id: str = Field(min_length=1, max_length=64)
    pack_version: str = Field(min_length=5, max_length=100)
    pack_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    display_name: str = Field(min_length=1, max_length=100)
    default_locale: str = Field(min_length=2, max_length=20)
    prompt: str = Field(min_length=1, max_length=256 * 1024)
    persona: str = Field(min_length=1, max_length=256 * 1024)
    theme: PackTheme
    provenance: Provenance

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        try:
            return validate_pack_id(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("display_name", "prompt", "persona")
    @classmethod
    def _validate_clean_text(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Runtime character text must be non-empty and contain no NUL bytes.")
        return value

    @classmethod
    def from_pack(cls, pack: ValidatedCharacterPack) -> RuntimeCharacter:
        return cls(
            schema_version=1,
            pack_id=pack.manifest.pack_id,
            pack_version=pack.manifest.version,
            pack_content_hash=pack.content_hash,
            display_name=pack.manifest.display_name,
            default_locale=pack.manifest.default_locale,
            prompt=pack.prompt,
            persona=pack.persona,
            theme=pack.theme,
            provenance=pack.manifest.provenance,
        )


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Serialize a model deterministically for hashing and artifact output."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def write_runtime_files(pack: ValidatedCharacterPack, artifact_dir: str | Path) -> None:
    """Write canonical runtime and evaluation inputs into a staging directory."""
    root = Path(artifact_dir)
    if not root.is_dir() or root.is_symlink():
        raise ArtifactValidationError(f"Artifact staging root must be a directory: {root}")
    runtime = RuntimeCharacter.from_pack(pack)
    (root / RUNTIME_DESCRIPTOR_FILENAME).write_bytes(canonical_json_bytes(runtime))
    (root / EVALUATION_ARTIFACT_FILENAME).write_bytes(canonical_json_bytes(pack.evaluation))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactValidationError(f"Duplicate JSON key in runtime descriptor: {key}")
        result[key] = value
    return result


def load_runtime_character(path: str | Path) -> RuntimeCharacter:
    """Load a strict runtime descriptor from an already verified artifact."""
    descriptor_path = Path(path)
    if not descriptor_path.is_file() or descriptor_path.is_symlink():
        raise ArtifactValidationError(
            f"Runtime descriptor must be a regular file: {descriptor_path}"
        )
    try:
        payload = json.loads(
            descriptor_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ArtifactValidationError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Unable to load runtime descriptor: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError("Runtime descriptor must contain a JSON object.")
    try:
        return RuntimeCharacter.model_validate(cast(dict[str, Any], payload))
    except ValidationError as exc:
        raise ArtifactValidationError(f"Invalid runtime descriptor: {exc}") from exc


def load_published_character(published: PublishedArtifact) -> RuntimeCharacter:
    """Load and cross-check runtime content against the artifact manifest."""
    character = load_runtime_character(published.path / RUNTIME_DESCRIPTOR_FILENAME)
    manifest = published.manifest
    if character.pack_id != manifest.pack_id:
        raise ArtifactValidationError("Runtime descriptor Pack id does not match its manifest.")
    if character.pack_version != manifest.pack_version:
        raise ArtifactValidationError(
            "Runtime descriptor Pack version does not match its manifest."
        )
    if character.pack_content_hash != manifest.pack_content_hash:
        raise ArtifactValidationError(
            "Runtime descriptor content hash does not match its manifest."
        )
    if character.provenance != manifest.provenance:
        raise ArtifactValidationError("Runtime descriptor provenance does not match its manifest.")
    return character
