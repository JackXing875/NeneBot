"""Content-addressed, atomically activated Character Pack artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
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

from src.knowledge.pack import (
    PackValidationError,
    Provenance,
    ValidatedCharacterPack,
    validate_pack_id,
)

ARTIFACT_MANIFEST_FILENAME = "artifact-manifest.json"
CURRENT_POINTER_FILENAME = "current.json"
ARTIFACT_SCHEMA_VERSION: Literal[1] = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class ArtifactValidationError(ValueError):
    """Raised when a staged or published artifact fails integrity validation."""


def _clean_text(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and have no surrounding whitespace.")
    if "\x00" in value:
        raise ValueError(f"{field_name} must not contain NUL bytes.")
    return value


def _relative_path(value: str) -> str:
    _clean_text(value, field_name="path")
    if "\\" in value:
        raise ValueError("Artifact paths must use forward slashes.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Artifact paths must be normalized relative paths without traversal.")
    if path.as_posix() != value:
        raise ValueError("Artifact paths must be normalized POSIX paths.")
    return value


class ArtifactFile(BaseModel):
    """Integrity metadata for one generated artifact file."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        value = _relative_path(value)
        if value == ARTIFACT_MANIFEST_FILENAME:
            raise ValueError("The manifest cannot list itself as a generated file.")
        return value


def _calculate_artifact_hash(
    *,
    pack_id: str,
    pack_version: str,
    artifact_version: str,
    pack_content_hash: str,
    pack_manifest_sha256: str,
    embedding_model: str,
    vector_dimension: int,
    record_count: int,
    provenance: Provenance,
    files: list[ArtifactFile],
) -> str:
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "artifact_version": artifact_version,
        "pack_content_hash": pack_content_hash,
        "pack_manifest_sha256": pack_manifest_sha256,
        "embedding_model": embedding_model,
        "vector_dimension": vector_dimension,
        "record_count": record_count,
        "provenance": provenance.model_dump(mode="json"),
        "files": [item.model_dump(mode="json") for item in files],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class ArtifactManifest(BaseModel):
    """Immutable build contract for a published vector/search artifact."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    pack_id: str = Field(min_length=1, max_length=64)
    pack_version: str = Field(min_length=5, max_length=100)
    artifact_version: str = Field(min_length=5, max_length=100)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str = Field(min_length=20, max_length=40)
    pack_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    pack_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_model: str = Field(min_length=1, max_length=300)
    vector_dimension: int = Field(gt=0, le=1_000_000)
    record_count: int = Field(ge=0)
    provenance: Provenance
    files: list[ArtifactFile] = Field(min_length=1)

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        try:
            return validate_pack_id(value)
        except PackValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("pack_version", "artifact_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if _SEMVER_RE.fullmatch(value) is None:
            raise ValueError("version must be valid semantic version text.")
        return value

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO 8601 timestamp.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("created_at must include a timezone.")
        return value

    @field_validator("embedding_model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        return _clean_text(value, field_name="embedding_model")

    @field_validator("files")
    @classmethod
    def _validate_files(cls, values: list[ArtifactFile]) -> list[ArtifactFile]:
        paths = [value.path for value in values]
        if paths != sorted(paths):
            raise ValueError("files must be sorted by path.")
        if len(paths) != len(set(paths)):
            raise ValueError("files must not contain duplicate paths.")
        return values

    @model_validator(mode="after")
    def _verify_artifact_hash(self) -> ArtifactManifest:
        expected = _calculate_artifact_hash(
            pack_id=self.pack_id,
            pack_version=self.pack_version,
            artifact_version=self.artifact_version,
            pack_content_hash=self.pack_content_hash,
            pack_manifest_sha256=self.pack_manifest_sha256,
            embedding_model=self.embedding_model,
            vector_dimension=self.vector_dimension,
            record_count=self.record_count,
            provenance=self.provenance,
            files=self.files,
        )
        if self.artifact_hash != expected:
            raise ValueError("artifact_hash does not match the manifest contents.")
        return self


class CurrentArtifactPointer(BaseModel):
    """Small pointer atomically replaced when a new immutable artifact activates."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_version: str = Field(min_length=5, max_length=100)
    relative_path: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("artifact_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if _SEMVER_RE.fullmatch(value) is None:
            raise ValueError("artifact_version must be valid semantic version text.")
        return value

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        value = _relative_path(value)
        if not value.startswith("versions/"):
            raise ValueError("Current artifact pointers must target versions/.")
        return value


@dataclass(frozen=True)
class PublishedArtifact:
    """A verified immutable artifact directory selected by the active pointer."""

    path: Path
    manifest: ArtifactManifest
    manifest_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_generated_files(root: Path) -> list[ArtifactFile]:
    files: list[ArtifactFile] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ArtifactValidationError(f"Artifact files must not use symlinks: {path}")
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        if relative_path == ARTIFACT_MANIFEST_FILENAME:
            continue
        files.append(
            ArtifactFile(
                path=relative_path,
                sha256=_sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return files


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_artifact_manifest(
    pack: ValidatedCharacterPack,
    artifact_dir: str | Path,
    *,
    artifact_version: str,
    embedding_model: str,
    vector_dimension: int,
    created_at: str | None = None,
) -> ArtifactManifest:
    """Hash staged output files and create a self-verifying manifest."""
    root = Path(artifact_dir)
    if not root.is_dir() or root.is_symlink():
        raise ArtifactValidationError(f"Artifact staging root must be a directory: {root}")
    files = _scan_generated_files(root)
    if not files:
        raise ArtifactValidationError("An artifact must contain at least one generated file.")

    artifact_hash = _calculate_artifact_hash(
        pack_id=pack.manifest.pack_id,
        pack_version=pack.manifest.version,
        artifact_version=artifact_version,
        pack_content_hash=pack.content_hash,
        pack_manifest_sha256=pack.manifest_sha256,
        embedding_model=embedding_model,
        vector_dimension=vector_dimension,
        record_count=len(pack.records),
        provenance=pack.manifest.provenance,
        files=files,
    )
    try:
        return ArtifactManifest(
            schema_version=ARTIFACT_SCHEMA_VERSION,
            pack_id=pack.manifest.pack_id,
            pack_version=pack.manifest.version,
            artifact_version=artifact_version,
            artifact_hash=artifact_hash,
            created_at=created_at or _utc_now(),
            pack_content_hash=pack.content_hash,
            pack_manifest_sha256=pack.manifest_sha256,
            embedding_model=embedding_model,
            vector_dimension=vector_dimension,
            record_count=len(pack.records),
            provenance=pack.manifest.provenance,
            files=files,
        )
    except ValidationError as exc:
        raise ArtifactValidationError(f"Invalid artifact build metadata: {exc}") from exc


def _canonical_model_bytes(model: BaseModel) -> bytes:
    payload = model.model_dump(mode="json")
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file_handle:
            file_handle.write(content)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_artifact_manifest(manifest: ArtifactManifest, artifact_dir: str | Path) -> Path:
    """Atomically write the canonical manifest into a staged artifact directory."""
    root = Path(artifact_dir)
    if not root.is_dir() or root.is_symlink():
        raise ArtifactValidationError(f"Artifact staging root must be a directory: {root}")
    path = root / ARTIFACT_MANIFEST_FILENAME
    _atomic_write(path, _canonical_model_bytes(manifest))
    return path


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except ArtifactValidationError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Unable to load artifact metadata at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError(f"Artifact metadata must be a JSON object: {path}")
    return cast(dict[str, Any], payload)


def load_artifact_manifest(path: str | Path) -> ArtifactManifest:
    """Load a manifest and verify its internal content hash."""
    manifest_path = Path(path)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ArtifactValidationError(f"Artifact manifest must be a regular file: {manifest_path}")
    try:
        return ArtifactManifest.model_validate(_load_json_object(manifest_path))
    except ValidationError as exc:
        raise ArtifactValidationError(
            f"Invalid artifact manifest at {manifest_path}: {exc}"
        ) from exc


def verify_artifact_directory(artifact_dir: str | Path) -> ArtifactManifest:
    """Verify manifest integrity, file hashes, sizes, and absence of extra files."""
    root = Path(artifact_dir)
    if not root.is_dir() or root.is_symlink():
        raise ArtifactValidationError(f"Artifact root must be a regular directory: {root}")
    manifest = load_artifact_manifest(root / ARTIFACT_MANIFEST_FILENAME)
    scanned_files = _scan_generated_files(root)
    expected = {item.path: item for item in manifest.files}
    actual = {item.path: item for item in scanned_files}
    if actual.keys() != expected.keys():
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        raise ArtifactValidationError(
            f"Artifact file set mismatch (missing={missing}, extra={extra})."
        )
    for path, expected_file in expected.items():
        actual_file = actual[path]
        if actual_file != expected_file:
            raise ArtifactValidationError(f"Artifact integrity check failed for {path}.")
    return manifest


class ArtifactStore:
    """Publish immutable versions and atomically switch a small active pointer."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _pack_root(self, pack_id: str, *, create: bool) -> Path:
        validate_pack_id(pack_id)
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir():
            raise ArtifactValidationError(f"Artifact store does not exist: {self.root}")
        if self.root.is_symlink():
            raise ArtifactValidationError("Artifact store root must not be a symlink.")
        pack_root = self.root.resolve() / pack_id
        if create:
            pack_root.mkdir(parents=True, exist_ok=True)
        elif not pack_root.is_dir():
            raise ArtifactValidationError(f"No artifact directory for pack {pack_id}.")
        if pack_root.is_symlink():
            raise ArtifactValidationError("Artifact pack root must not be a symlink.")
        return pack_root

    @contextmanager
    def stage(self, pack_id: str) -> Iterator[Path]:
        """Create same-filesystem temporary output and remove it unless published."""
        pack_root = self._pack_root(pack_id, create=True)
        stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=pack_root))
        try:
            yield stage
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def publish(self, staged_dir: str | Path) -> PublishedArtifact:
        """Move a verified stage into immutable versions, then atomically activate it."""
        stage = Path(staged_dir)
        manifest = verify_artifact_directory(stage)
        pack_root = self._pack_root(manifest.pack_id, create=True)
        if stage.parent.resolve() != pack_root.resolve() or not stage.name.startswith(".staging-"):
            raise ArtifactValidationError(
                "Artifacts may only be published from this store's stage()."
            )

        versions_root = pack_root / "versions"
        versions_root.mkdir(exist_ok=True)
        destination = versions_root / (f"{manifest.artifact_version}-{manifest.artifact_hash[:12]}")
        if destination.exists():
            existing = verify_artifact_directory(destination)
            if existing.artifact_hash != manifest.artifact_hash:
                raise ArtifactValidationError(f"Artifact version collision at {destination}.")
            shutil.rmtree(stage)
        else:
            os.replace(stage, destination)
            _fsync_directory(versions_root)

        manifest_path = destination / ARTIFACT_MANIFEST_FILENAME
        manifest_sha256 = _sha256_file(manifest_path)
        pointer = CurrentArtifactPointer(
            schema_version=ARTIFACT_SCHEMA_VERSION,
            artifact_hash=manifest.artifact_hash,
            artifact_version=manifest.artifact_version,
            relative_path=destination.relative_to(pack_root).as_posix(),
            manifest_sha256=manifest_sha256,
        )
        _atomic_write(pack_root / CURRENT_POINTER_FILENAME, _canonical_model_bytes(pointer))
        return PublishedArtifact(
            path=destination,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )

    def resolve_current(self, pack_id: str) -> PublishedArtifact:
        """Resolve and re-verify the currently active immutable artifact."""
        pack_root = self._pack_root(pack_id, create=False)
        pointer_path = pack_root / CURRENT_POINTER_FILENAME
        if not pointer_path.is_file() or pointer_path.is_symlink():
            raise ArtifactValidationError(f"No active artifact for pack {pack_id}.")
        try:
            pointer = CurrentArtifactPointer.model_validate(_load_json_object(pointer_path))
        except ValidationError as exc:
            raise ArtifactValidationError(f"Invalid active artifact pointer: {exc}") from exc

        destination = (pack_root / pointer.relative_path).resolve()
        if not destination.is_relative_to(pack_root.resolve()):
            raise ArtifactValidationError("Active artifact pointer escapes its pack root.")
        manifest = verify_artifact_directory(destination)
        manifest_path = destination / ARTIFACT_MANIFEST_FILENAME
        manifest_sha256 = _sha256_file(manifest_path)
        if manifest.artifact_hash != pointer.artifact_hash:
            raise ArtifactValidationError("Active pointer artifact hash mismatch.")
        if manifest.artifact_version != pointer.artifact_version:
            raise ArtifactValidationError("Active pointer artifact version mismatch.")
        if manifest_sha256 != pointer.manifest_sha256:
            raise ArtifactValidationError("Active pointer manifest hash mismatch.")
        return PublishedArtifact(
            path=destination,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )
