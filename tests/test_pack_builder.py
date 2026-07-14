import json
import shutil
from pathlib import Path

import pytest

from src.knowledge.artifacts import ArtifactStore, ArtifactValidationError
from src.knowledge.builder import (
    artifact_runtime_files,
    build_pack_artifact,
    evaluate_loaded_artifact,
    load_artifact,
)
from src.knowledge.editor import derive_pack_without_sources
from src.knowledge.pack import calculate_knowledge_content_sha256, validate_character_pack


class DeterministicEncoder:
    model_name = "test/deterministic-v1"

    def __init__(self, dimension: int = 32) -> None:
        self.dimension = dimension
        self._indices: dict[str, int] = {}

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            index = self._indices.setdefault(text, len(self._indices)) % self.dimension
            vector = [0.0] * self.dimension
            vector[index] = 1.0
            vectors.append(vector)
        return vectors


def demo_pack_path() -> Path:
    return Path(__file__).resolve().parents[1] / "packs" / "demo"


def test_builder_installs_verified_artifact_without_activating(tmp_path: Path) -> None:
    encoder = DeterministicEncoder()
    published = build_pack_artifact(
        demo_pack_path(),
        tmp_path / "artifacts",
        encoder,
        activate=False,
        created_at="2026-07-14T00:00:00Z",
    )

    assert artifact_runtime_files().issubset(
        {path.name for path in published.path.iterdir() if path.is_file()}
    )
    assert published.manifest.record_count == 10
    assert published.manifest.embedding_model == encoder.model_name
    assert published.manifest.vector_dimension == encoder.dimension
    with pytest.raises(ArtifactValidationError, match="No active artifact"):
        ArtifactStore(tmp_path / "artifacts").resolve_current("mira-demo")


def test_builder_preserves_provenance_and_passes_pack_evaluation(tmp_path: Path) -> None:
    encoder = DeterministicEncoder()
    published = build_pack_artifact(
        demo_pack_path(),
        tmp_path / "artifacts",
        encoder,
        activate=True,
        created_at="2026-07-14T00:00:00Z",
    )
    loaded = load_artifact(published)
    pack = validate_character_pack(demo_pack_path())
    report = evaluate_loaded_artifact(loaded, pack.evaluation, encoder)

    assert loaded.character.display_name == "米拉 / Mira"
    assert loaded.vector_store.index.ntotal == 10
    first_record = loaded.vector_store.metadata[0]
    assert first_record["record_id"] == "greeting-first"
    assert first_record["content_sha256"] == pack.records[0].content_sha256
    assert first_record["provenance"]["license"] == "CC0-1.0"
    assert first_record["safety"]["reviewed"] is True
    assert report.passed is True
    assert len(report.results) == 6


def test_store_can_promote_and_rollback_between_installed_versions(tmp_path: Path) -> None:
    store_root = tmp_path / "artifacts"
    encoder = DeterministicEncoder()
    first = build_pack_artifact(
        demo_pack_path(),
        store_root,
        encoder,
        artifact_version="1.0.0",
        activate=False,
        created_at="2026-07-14T00:00:00Z",
    )
    second = build_pack_artifact(
        demo_pack_path(),
        store_root,
        encoder,
        artifact_version="1.1.0",
        activate=False,
        created_at="2026-07-14T01:00:00Z",
    )
    store = ArtifactStore(store_root)

    store.activate("mira-demo", first.manifest.artifact_hash)
    store.activate("mira-demo", second.manifest.artifact_hash)
    rolled_back = store.rollback("mira-demo")

    assert rolled_back.path == first.path
    assert store.resolve_current("mira-demo").path == first.path


def test_publish_lock_prevents_concurrent_activation(tmp_path: Path) -> None:
    store_root = tmp_path / "artifacts"
    encoder = DeterministicEncoder()
    published = build_pack_artifact(
        demo_pack_path(),
        store_root,
        encoder,
        activate=False,
        created_at="2026-07-14T00:00:00Z",
    )
    lock_path = store_root / "mira-demo" / ".publish.lock"
    lock_path.write_text("held", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="already active"):
        ArtifactStore(store_root).activate("mira-demo", published.manifest.artifact_hash)


def test_derive_pack_removes_a_source_and_can_rebuild(tmp_path: Path) -> None:
    source_pack = tmp_path / "source-pack"
    shutil.copytree(demo_pack_path(), source_pack)
    knowledge_path = source_pack / "knowledge.jsonl"
    records = [json.loads(line) for line in knowledge_path.read_text(encoding="utf-8").splitlines()]
    retired_source = "private-import/source-a.jsonl"
    records[0]["provenance"]["source"] = retired_source
    records[0]["content_sha256"] = calculate_knowledge_content_sha256(
        trigger=records[0]["trigger"],
        response=records[0]["response"],
        tags=records[0]["tags"],
        provenance=validate_character_pack(demo_pack_path())
        .records[0]
        .provenance.model_copy(update={"source": retired_source}),
        safety=validate_character_pack(demo_pack_path()).records[0].safety,
    )
    knowledge_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    output = tmp_path / "derived-pack"
    report = derive_pack_without_sources(
        source_pack,
        output,
        version="1.1.0",
        excluded_sources={retired_source},
    )
    published = build_pack_artifact(
        output,
        tmp_path / "artifacts",
        DeterministicEncoder(),
        activate=True,
    )

    assert report.pack.manifest.version == "1.1.0"
    assert report.removed_record_ids == ("greeting-first",)
    assert "eval-greeting" in report.removed_evaluation_case_ids
    assert published.manifest.record_count == 9
