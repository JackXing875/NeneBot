"""Strict, rights-aware Character Pack validation.

This module intentionally does not understand the legacy ChatML dataset.  A Character
Pack is an authored source bundle with explicit provenance.  Runtime/vector artifacts
are built from a validated pack in a separate step.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

PACK_MANIFEST_FILENAME = "manifest.json"
PACK_SCHEMA_VERSION = 1
KNOWLEDGE_SCHEMA_VERSION = 1
MAX_PERSONA_BYTES = 256 * 1024
MAX_PROMPT_BYTES = 256 * 1024
MAX_KNOWLEDGE_BYTES = 64 * 1024 * 1024
MAX_EVALUATION_BYTES = 2 * 1024 * 1024
MAX_THEME_BYTES = 64 * 1024

_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_LOCALE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-[A-Z]{2}|-\d{3})?$")

RightsBasis = Literal["owned", "licensed", "public-domain"]
SafetyClassification = Literal["general", "sensitive"]


class PackValidationError(ValueError):
    """Raised when a Character Pack cannot be trusted as a build input."""


def validate_pack_id(value: str) -> str:
    """Return a safe pack id or raise ``PackValidationError``."""
    if len(value) > 64 or _PACK_ID_RE.fullmatch(value) is None:
        raise PackValidationError(
            "pack_id must be a lowercase kebab-case identifier of at most 64 characters."
        )
    return value


def _require_clean_text(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and have no surrounding whitespace.")
    if "\x00" in value:
        raise ValueError(f"{field_name} must not contain NUL bytes.")
    return value


def _validate_relative_path(value: str, *, suffix: str | None = None) -> str:
    _require_clean_text(value, field_name="path")
    if "\\" in value:
        raise ValueError("Pack paths must use forward slashes.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Pack paths must be normalized relative paths without traversal.")
    if path.as_posix() != value:
        raise ValueError("Pack paths must be normalized POSIX paths.")
    if suffix is not None and path.suffix.lower() != suffix:
        raise ValueError(f"Pack path must end in {suffix}.")
    return value


class Provenance(BaseModel):
    """Rights metadata required at both pack and record level."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    creator: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    license: str = Field(min_length=1, max_length=100)
    rights: RightsBasis

    @field_validator("creator", "source", "license")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _require_clean_text(value, field_name=str(info.field_name))


class SafetyReview(BaseModel):
    """Explicit safety disposition for one knowledge record."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    classification: SafetyClassification
    reviewed: bool
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_clean_text(value, field_name="notes")

    @model_validator(mode="after")
    def _require_completed_review(self) -> SafetyReview:
        if not self.reviewed:
            raise ValueError("Every published knowledge record must be safety reviewed.")
        return self


class EvaluationCase(BaseModel):
    """Deterministic retrieval expectation shipped with a Character Pack."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=4_000)
    expected_record_ids: list[str] = Field(min_length=1, max_length=10)
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if _RECORD_ID_RE.fullmatch(value) is None:
            raise ValueError("id contains unsupported characters.")
        return value

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        return _require_clean_text(value, field_name="query")

    @field_validator("expected_record_ids")
    @classmethod
    def _validate_expected_record_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("expected_record_ids must be unique.")
        for value in values:
            if _RECORD_ID_RE.fullmatch(value) is None:
                raise ValueError("expected_record_ids contains an unsupported record id.")
        return values


class EvaluationSuite(BaseModel):
    """Versioned offline evaluation cases for one Pack."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    cases: list[EvaluationCase] = Field(min_length=1, max_length=200)

    @field_validator("cases")
    @classmethod
    def _validate_unique_case_ids(cls, values: list[EvaluationCase]) -> list[EvaluationCase]:
        case_ids = [case.id for case in values]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Evaluation case ids must be unique.")
        return values


class ThemeAvatar(BaseModel):
    """Code-native avatar configuration; public Packs need no bundled character art."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["initials"]
    text: str = Field(min_length=1, max_length=4)

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _require_clean_text(value, field_name="avatar.text")


class PackTheme(BaseModel):
    """Small, validated theme contract consumed by current and future clients."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    avatar: ThemeAvatar


def calculate_knowledge_content_sha256(
    *,
    trigger: str,
    response: str,
    tags: list[str],
    provenance: Provenance,
    safety: SafetyReview,
) -> str:
    """Hash the canonical, provenance-preserving content of one knowledge unit."""
    payload = {
        "trigger": trigger,
        "response": response,
        "tags": tags,
        "provenance": provenance.model_dump(mode="json"),
        "safety": safety.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class KnowledgeRecord(BaseModel):
    """Canonical v1 knowledge unit used by Character Packs."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    id: str = Field(min_length=1, max_length=128)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trigger: str = Field(min_length=1, max_length=4_000)
    response: str = Field(min_length=1, max_length=8_000)
    tags: list[str] = Field(default_factory=list, max_length=32)
    provenance: Provenance
    safety: SafetyReview

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if _RECORD_ID_RE.fullmatch(value) is None:
            raise ValueError("id contains unsupported characters.")
        return value

    @field_validator("trigger", "response")
    @classmethod
    def _validate_content(cls, value: str, info: Any) -> str:
        return _require_clean_text(value, field_name=str(info.field_name))

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            clean = _require_clean_text(value, field_name="tag")
            if len(clean) > 64:
                raise ValueError("tags must be at most 64 characters each.")
            normalized.append(clean)
        if len(set(normalized)) != len(normalized):
            raise ValueError("tags must be unique.")
        if normalized != sorted(normalized):
            raise ValueError("tags must be sorted for deterministic hashing.")
        return normalized

    @model_validator(mode="after")
    def _verify_content_sha256(self) -> KnowledgeRecord:
        expected = calculate_knowledge_content_sha256(
            trigger=self.trigger,
            response=self.response,
            tags=self.tags,
            provenance=self.provenance,
            safety=self.safety,
        )
        if self.content_sha256 != expected:
            raise ValueError("content_sha256 does not match canonical record content.")
        return self


class CharacterPackManifest(BaseModel):
    """Authored metadata describing one immutable Character Pack version."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    pack_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=5, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    default_locale: str = Field(min_length=2, max_length=20)
    persona_path: str
    prompt_path: str
    knowledge_path: str
    evaluation_path: str
    theme_path: str
    provenance: Provenance

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        try:
            return validate_pack_id(value)
        except PackValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if _SEMVER_RE.fullmatch(value) is None:
            raise ValueError("version must be valid semantic version text.")
        return value

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _require_clean_text(value, field_name="display_name")

    @field_validator("default_locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        if _LOCALE_RE.fullmatch(value) is None:
            raise ValueError("default_locale must be a normalized BCP 47 language tag.")
        return value

    @field_validator("persona_path")
    @classmethod
    def _validate_persona_path(cls, value: str) -> str:
        return _validate_relative_path(value, suffix=".md")

    @field_validator("prompt_path")
    @classmethod
    def _validate_prompt_path(cls, value: str) -> str:
        return _validate_relative_path(value, suffix=".md")

    @field_validator("knowledge_path")
    @classmethod
    def _validate_knowledge_path(cls, value: str) -> str:
        return _validate_relative_path(value, suffix=".jsonl")

    @field_validator("evaluation_path", "theme_path")
    @classmethod
    def _validate_json_path(cls, value: str) -> str:
        return _validate_relative_path(value, suffix=".json")


@dataclass(frozen=True)
class ValidatedCharacterPack:
    """A fully checked pack plus hashes used to derive artifacts."""

    root: Path
    manifest: CharacterPackManifest
    records: tuple[KnowledgeRecord, ...]
    persona: str
    prompt: str
    evaluation: EvaluationSuite
    theme: PackTheme
    manifest_sha256: str
    persona_sha256: str
    prompt_sha256: str
    knowledge_sha256: str
    evaluation_sha256: str
    theme_sha256: str
    content_hash: str


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json_object(text: str, *, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except PackValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise PackValidationError(f"Invalid JSON in {source}: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise PackValidationError(f"{source} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _format_validation_error(source: str, exc: ValidationError) -> PackValidationError:
    issues = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        issues.append(f"{location}: {error['msg']}")
    return PackValidationError(f"Invalid {source}: {'; '.join(issues)}")


def load_pack_manifest(path: Path) -> CharacterPackManifest:
    """Load a strict JSON pack manifest."""
    if not path.is_file() or path.is_symlink():
        raise PackValidationError(f"Pack manifest must be a regular file: {path}")
    payload = _parse_json_object(path.read_text(encoding="utf-8"), source=str(path))
    try:
        return CharacterPackManifest.model_validate(payload)
    except ValidationError as exc:
        raise _format_validation_error(str(path), exc) from exc


def _load_json_model(path: Path, model: type[BaseModel]) -> BaseModel:
    payload = _parse_json_object(path.read_text(encoding="utf-8"), source=str(path))
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise _format_validation_error(str(path), exc) from exc


def load_evaluation_suite(path: Path) -> EvaluationSuite:
    """Load a strict evaluation suite from a regular JSON file."""
    if not path.is_file() or path.is_symlink():
        raise PackValidationError(f"Evaluation suite must be a regular file: {path}")
    if path.stat().st_size > MAX_EVALUATION_BYTES:
        raise PackValidationError(
            f"Evaluation suite exceeds the {MAX_EVALUATION_BYTES}-byte validation limit."
        )
    return cast(EvaluationSuite, _load_json_model(path, EvaluationSuite))


def load_pack_theme(path: Path) -> PackTheme:
    """Load a strict code-native Pack theme."""
    if not path.is_file() or path.is_symlink():
        raise PackValidationError(f"Pack theme must be a regular file: {path}")
    if path.stat().st_size > MAX_THEME_BYTES:
        raise PackValidationError(f"Pack theme exceeds the {MAX_THEME_BYTES}-byte limit.")
    return cast(PackTheme, _load_json_model(path, PackTheme))


def load_knowledge_records(path: Path) -> tuple[KnowledgeRecord, ...]:
    """Load strict JSONL records and reject blanks, duplicates, and unknown fields."""
    if not path.is_file() or path.is_symlink():
        raise PackValidationError(f"Knowledge file must be a regular file: {path}")
    if path.stat().st_size > MAX_KNOWLEDGE_BYTES:
        raise PackValidationError(
            f"Knowledge file exceeds the {MAX_KNOWLEDGE_BYTES}-byte validation limit."
        )

    records: list[KnowledgeRecord] = []
    record_ids: set[str] = set()
    content_hashes: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            raise PackValidationError(f"Blank JSONL line at {path}:{line_number}.")
        payload = _parse_json_object(raw_line, source=f"{path}:{line_number}")
        try:
            record = KnowledgeRecord.model_validate(payload)
        except ValidationError as exc:
            raise _format_validation_error(f"{path}:{line_number}", exc) from exc
        if record.id in record_ids:
            raise PackValidationError(f"Duplicate knowledge record id at {path}:{line_number}.")
        if record.content_sha256 in content_hashes:
            raise PackValidationError(
                f"Duplicate knowledge record content at {path}:{line_number}."
            )
        record_ids.add(record.id)
        content_hashes.add(record.content_sha256)
        records.append(record)

    if not records:
        raise PackValidationError(f"Knowledge file is empty: {path}")
    return tuple(records)


def _resolve_pack_file(root: Path, relative_path: str) -> Path:
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise PackValidationError(f"Pack files must not use symlinks: {current}")
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise PackValidationError(f"Pack file is unavailable: {current}") from exc
    if not resolved.is_relative_to(root.resolve()):
        raise PackValidationError(f"Pack path escapes its root: {relative_path}")
    if not resolved.is_file():
        raise PackValidationError(f"Pack path is not a regular file: {relative_path}")
    return resolved


def _build_content_hash(
    *,
    manifest_sha256: str,
    persona_sha256: str,
    prompt_sha256: str,
    knowledge_sha256: str,
    evaluation_sha256: str,
    theme_sha256: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(b"character-pack-v1\0")
    for label, value in (
        ("manifest", manifest_sha256),
        ("persona", persona_sha256),
        ("prompt", prompt_sha256),
        ("knowledge", knowledge_sha256),
        ("evaluation", evaluation_sha256),
        ("theme", theme_sha256),
    ):
        digest.update(label.encode("ascii"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def validate_character_pack(pack_dir: str | Path) -> ValidatedCharacterPack:
    """Validate every authored input and return content-addressed pack metadata."""
    root = Path(pack_dir)
    if not root.is_dir() or root.is_symlink():
        raise PackValidationError(f"Character Pack root must be a regular directory: {root}")
    root = root.resolve()

    manifest_path = _resolve_pack_file(root, PACK_MANIFEST_FILENAME)
    manifest_bytes = manifest_path.read_bytes()
    manifest = load_pack_manifest(manifest_path)
    persona_path = _resolve_pack_file(root, manifest.persona_path)
    prompt_path = _resolve_pack_file(root, manifest.prompt_path)
    knowledge_path = _resolve_pack_file(root, manifest.knowledge_path)
    evaluation_path = _resolve_pack_file(root, manifest.evaluation_path)
    theme_path = _resolve_pack_file(root, manifest.theme_path)

    persona_bytes = persona_path.read_bytes()
    if not persona_bytes.strip():
        raise PackValidationError("Persona file must not be empty.")
    if len(persona_bytes) > MAX_PERSONA_BYTES:
        raise PackValidationError(
            f"Persona file exceeds the {MAX_PERSONA_BYTES}-byte validation limit."
        )

    prompt_bytes = prompt_path.read_bytes()
    if not prompt_bytes.strip():
        raise PackValidationError("Prompt file must not be empty.")
    if len(prompt_bytes) > MAX_PROMPT_BYTES:
        raise PackValidationError(
            f"Prompt file exceeds the {MAX_PROMPT_BYTES}-byte validation limit."
        )

    try:
        persona = persona_bytes.decode("utf-8")
        prompt = prompt_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackValidationError("Persona and prompt files must be valid UTF-8.") from exc
    if "\x00" in persona or "\x00" in prompt:
        raise PackValidationError("Persona and prompt files must not contain NUL bytes.")

    records = load_knowledge_records(knowledge_path)
    evaluation = load_evaluation_suite(evaluation_path)
    theme = load_pack_theme(theme_path)
    record_ids = {record.id for record in records}
    for case in evaluation.cases:
        missing = sorted(set(case.expected_record_ids) - record_ids)
        if missing:
            raise PackValidationError(
                f"Evaluation case {case.id!r} references unknown records: {missing}."
            )
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    persona_sha256 = _sha256_bytes(persona_bytes)
    prompt_sha256 = _sha256_bytes(prompt_bytes)
    knowledge_sha256 = _sha256_bytes(knowledge_path.read_bytes())
    evaluation_sha256 = _sha256_bytes(evaluation_path.read_bytes())
    theme_sha256 = _sha256_bytes(theme_path.read_bytes())

    return ValidatedCharacterPack(
        root=root,
        manifest=manifest,
        records=records,
        persona=persona,
        prompt=prompt,
        evaluation=evaluation,
        theme=theme,
        manifest_sha256=manifest_sha256,
        persona_sha256=persona_sha256,
        prompt_sha256=prompt_sha256,
        knowledge_sha256=knowledge_sha256,
        evaluation_sha256=evaluation_sha256,
        theme_sha256=theme_sha256,
        content_hash=_build_content_hash(
            manifest_sha256=manifest_sha256,
            persona_sha256=persona_sha256,
            prompt_sha256=prompt_sha256,
            knowledge_sha256=knowledge_sha256,
            evaluation_sha256=evaluation_sha256,
            theme_sha256=theme_sha256,
        ),
    )
