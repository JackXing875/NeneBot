"""Offline Character Pack artifact builder and deterministic retrieval evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.knowledge.artifacts import (
    ArtifactStore,
    ArtifactValidationError,
    PublishedArtifact,
    build_artifact_manifest,
    verify_artifact_directory,
    write_artifact_manifest,
)
from src.knowledge.pack import EvaluationSuite, validate_character_pack
from src.knowledge.runtime import (
    EVALUATION_ARTIFACT_FILENAME,
    RUNTIME_DESCRIPTOR_FILENAME,
    RuntimeCharacter,
    load_published_character,
    write_runtime_files,
)

INDEX_FILENAME = "faiss_index.bin"
METADATA_FILENAME = "knowledge_base.json"


class EmbeddingEncoder(Protocol):
    """Minimal boundary needed by offline build and evaluation."""

    model_name: str

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Return one dense vector per input text."""


@dataclass(frozen=True)
class LoadedArtifact:
    """Verified runtime character and retrieval store."""

    published: PublishedArtifact
    character: RuntimeCharacter
    vector_store: FaissVectorStore


@dataclass(frozen=True)
class EvaluationResult:
    """One deterministic retrieval evaluation outcome."""

    case_id: str
    passed: bool
    expected_record_ids: tuple[str, ...]
    retrieved_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregate offline evaluation report."""

    pack_id: str
    artifact_hash: str
    results: tuple[EvaluationResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)


def _validate_embeddings(
    embeddings: list[list[float]],
    *,
    expected_count: int,
) -> int:
    if len(embeddings) != expected_count:
        raise ArtifactValidationError(
            f"Embedding encoder returned {len(embeddings)} vectors for {expected_count} records."
        )
    if not embeddings or not embeddings[0]:
        raise ArtifactValidationError("Embedding encoder returned no vector dimensions.")
    dimension = len(embeddings[0])
    if any(len(vector) != dimension for vector in embeddings):
        raise ArtifactValidationError("Embedding vectors must all have the same dimension.")
    return dimension


def build_pack_artifact(
    pack_dir: str | Path,
    artifact_store_dir: str | Path,
    encoder: EmbeddingEncoder,
    *,
    artifact_version: str | None = None,
    activate: bool = False,
    created_at: str | None = None,
) -> PublishedArtifact:
    """Build, verify, and install one immutable artifact entirely offline."""
    pack = validate_character_pack(pack_dir)
    embeddings = encoder.encode([record.trigger for record in pack.records])
    dimension = _validate_embeddings(embeddings, expected_count=len(pack.records))
    store = ArtifactStore(artifact_store_dir)

    with store.stage(pack.manifest.pack_id) as stage:
        write_runtime_files(pack, stage)
        vector_store = FaissVectorStore(
            dimension=dimension,
            index_path=str(stage / INDEX_FILENAME),
            meta_path=str(stage / METADATA_FILENAME),
        )
        metadata = [
            {
                "record_id": record.id,
                "content_sha256": record.content_sha256,
                "bot_response": record.response,
                "tags": record.tags,
                "provenance": record.provenance.model_dump(mode="json"),
                "safety": record.safety.model_dump(mode="json"),
                "pack_id": pack.manifest.pack_id,
                "pack_version": pack.manifest.version,
            }
            for record in pack.records
        ]
        vector_store.add_texts(
            texts=[record.trigger for record in pack.records],
            embeddings=embeddings,
            metadata=metadata,
        )
        manifest = build_artifact_manifest(
            pack,
            stage,
            artifact_version=artifact_version or pack.manifest.version,
            embedding_model=encoder.model_name,
            vector_dimension=dimension,
            created_at=created_at,
        )
        write_artifact_manifest(manifest, stage)
        verify_artifact_directory(stage)
        return store.publish(stage, activate=activate)


def load_artifact(published: PublishedArtifact) -> LoadedArtifact:
    """Load and cross-check every runtime file from a verified artifact."""
    verify_artifact_directory(published.path)
    character = load_published_character(published)
    vector_store = FaissVectorStore(
        dimension=published.manifest.vector_dimension,
        index_path=str(published.path / INDEX_FILENAME),
        meta_path=str(published.path / METADATA_FILENAME),
    )
    if vector_store.index.ntotal != published.manifest.record_count:
        raise ArtifactValidationError("Artifact vector count does not match its manifest.")
    if len(vector_store.metadata) != published.manifest.record_count:
        raise ArtifactValidationError("Artifact metadata count does not match its manifest.")
    required_metadata = {
        "record_id",
        "content_sha256",
        "bot_response",
        "provenance",
        "safety",
        "pack_id",
        "pack_version",
    }
    for record in vector_store.metadata:
        if not isinstance(record, dict):
            raise ArtifactValidationError("Artifact metadata records must be JSON objects.")
        if not required_metadata.issubset(record):
            raise ArtifactValidationError("Artifact record is missing provenance metadata.")
        if record["pack_id"] != published.manifest.pack_id:
            raise ArtifactValidationError("Artifact record Pack id mismatch.")
        if record["pack_version"] != published.manifest.pack_version:
            raise ArtifactValidationError("Artifact record Pack version mismatch.")
        provenance = record["provenance"]
        safety = record["safety"]
        if not isinstance(provenance, dict) or not {
            "creator",
            "source",
            "license",
            "rights",
        }.issubset(provenance):
            raise ArtifactValidationError("Artifact record provenance is incomplete.")
        if not isinstance(safety, dict) or safety.get("reviewed") is not True:
            raise ArtifactValidationError("Artifact record safety review is incomplete.")
    return LoadedArtifact(
        published=published,
        character=character,
        vector_store=vector_store,
    )


def evaluate_loaded_artifact(
    artifact: LoadedArtifact,
    evaluation: EvaluationSuite,
    encoder: EmbeddingEncoder,
) -> EvaluationReport:
    """Evaluate retrieval expectations without invoking an LLM."""
    if encoder.model_name != artifact.published.manifest.embedding_model:
        raise ArtifactValidationError(
            "Evaluation encoder does not match the artifact embedding model."
        )
    results: list[EvaluationResult] = []
    for case in evaluation.cases:
        vectors = encoder.encode([case.query])
        dimension = _validate_embeddings(vectors, expected_count=1)
        if dimension != artifact.published.manifest.vector_dimension:
            raise ArtifactValidationError(
                "Evaluation embedding dimension does not match the artifact."
            )
        retrieved = artifact.vector_store.search(vectors[0], top_k=case.top_k)
        retrieved_ids = tuple(str(item.get("record_id", "")) for item in retrieved)
        expected_ids = tuple(case.expected_record_ids)
        results.append(
            EvaluationResult(
                case_id=case.id,
                passed=all(record_id in retrieved_ids for record_id in expected_ids),
                expected_record_ids=expected_ids,
                retrieved_record_ids=retrieved_ids,
            )
        )
    return EvaluationReport(
        pack_id=artifact.character.pack_id,
        artifact_hash=artifact.published.manifest.artifact_hash,
        results=tuple(results),
    )


def artifact_runtime_files() -> frozenset[str]:
    """Expose the required file contract for diagnostics and tests."""
    return frozenset(
        {
            INDEX_FILENAME,
            METADATA_FILENAME,
            RUNTIME_DESCRIPTOR_FILENAME,
            EVALUATION_ARTIFACT_FILENAME,
        }
    )
