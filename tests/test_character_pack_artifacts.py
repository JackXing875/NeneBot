import json
from pathlib import Path

import pytest

from src.knowledge.artifacts import (
    ARTIFACT_MANIFEST_FILENAME,
    ArtifactStore,
    ArtifactValidationError,
    build_artifact_manifest,
    verify_artifact_directory,
    write_artifact_manifest,
)
from src.knowledge.pack import (
    PackValidationError,
    Provenance,
    SafetyReview,
    calculate_knowledge_content_sha256,
    validate_character_pack,
)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "pack_id": "demo-companion",
        "version": "1.0.0",
        "display_name": "Demo Companion",
        "default_locale": "zh-CN",
        "persona_path": "persona.md",
        "prompt_path": "prompt.md",
        "knowledge_path": "knowledge.jsonl",
        "evaluation_path": "evaluation.json",
        "theme_path": "theme.json",
        "provenance": {
            "creator": "Persona Studio contributors",
            "source": "Original test fixture",
            "license": "CC0-1.0",
            "rights": "owned",
        },
    }


def _record(record_id: str = "greeting-1") -> dict[str, object]:
    trigger = "你好"
    response = "你好，很高兴见到你。"
    tags = ["greeting"]
    provenance = {
        "creator": "Persona Studio contributors",
        "source": "Original test fixture line 1",
        "license": "CC0-1.0",
        "rights": "owned",
    }
    safety = {
        "classification": "general",
        "reviewed": True,
        "notes": "Synthetic fixture",
    }
    content_sha256 = calculate_knowledge_content_sha256(
        trigger=trigger,
        response=response,
        tags=tags,
        provenance=Provenance.model_validate(provenance),
        safety=SafetyReview.model_validate(safety),
    )
    return {
        "schema_version": 1,
        "id": record_id,
        "content_sha256": content_sha256,
        "trigger": trigger,
        "response": response,
        "tags": tags,
        "provenance": provenance,
        "safety": safety,
    }


def _write_pack(root: Path, records: list[dict[str, object]] | None = None) -> Path:
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(_manifest(), ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "persona.md").write_text("# Demo\n\n你是一位友好的原创助手。\n", encoding="utf-8")
    (root / "prompt.md").write_text("请以友好、诚实的方式回复。\n", encoding="utf-8")
    selected_records = records or [_record()]
    (root / "knowledge.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in selected_records),
        encoding="utf-8",
    )
    (root / "evaluation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "greeting-eval",
                        "query": "你好",
                        "expected_record_ids": [selected_records[0]["id"]],
                        "top_k": 1,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "theme.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "primary_color": "#7C83FD",
                "accent_color": "#5EEAD4",
                "background_color": "#111827",
                "avatar": {"kind": "initials", "text": "D"},
            }
        ),
        encoding="utf-8",
    )
    return root


def _stage_artifact(
    store: ArtifactStore,
    pack_dir: Path,
    *,
    artifact_version: str,
    content: bytes,
):
    pack = validate_character_pack(pack_dir)
    context = store.stage(pack.manifest.pack_id)
    stage = context.__enter__()
    (stage / "index.bin").write_bytes(content)
    (stage / "metadata.json").write_text('{"records":1}\n', encoding="utf-8")
    manifest = build_artifact_manifest(
        pack,
        stage,
        artifact_version=artifact_version,
        embedding_model="example/embedding-v1",
        vector_dimension=8,
        created_at="2026-07-13T00:00:00Z",
    )
    write_artifact_manifest(manifest, stage)
    return context, stage, manifest


def test_valid_character_pack_is_content_addressed(tmp_path: Path) -> None:
    pack = validate_character_pack(_write_pack(tmp_path / "pack"))

    assert pack.manifest.pack_id == "demo-companion"
    assert pack.records[0].provenance.license == "CC0-1.0"
    assert pack.records[0].safety.reviewed is True
    assert pack.prompt.startswith("请以友好")
    assert pack.evaluation.cases[0].expected_record_ids == ["greeting-1"]
    assert pack.theme.avatar.text == "D"
    assert len(pack.content_hash) == 64
    assert len(pack.manifest_sha256) == 64


def test_character_pack_rejects_unknown_fields_and_duplicate_ids(tmp_path: Path) -> None:
    first = _record()
    first["unreviewed_extra"] = True
    pack_dir = _write_pack(tmp_path / "pack", [first])

    with pytest.raises(PackValidationError, match="unreviewed_extra"):
        validate_character_pack(pack_dir)

    (pack_dir / "knowledge.jsonl").write_text(
        json.dumps(_record()) + "\n" + json.dumps(_record()) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PackValidationError, match="Duplicate knowledge record id"):
        validate_character_pack(pack_dir)


def test_character_pack_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    manifest = _manifest()
    manifest["persona_path"] = "../persona.md"
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PackValidationError, match="traversal"):
        validate_character_pack(pack_dir)


def test_character_pack_rejects_record_content_tampering(tmp_path: Path) -> None:
    record = _record()
    record["response"] = "内容已被篡改，但哈希没有更新。"
    pack_dir = _write_pack(tmp_path / "pack", [record])

    with pytest.raises(PackValidationError, match="content_sha256"):
        validate_character_pack(pack_dir)


def test_character_pack_requires_completed_safety_review(tmp_path: Path) -> None:
    record = _record()
    record["safety"] = {
        "classification": "general",
        "reviewed": False,
        "notes": "Review still pending",
    }
    pack_dir = _write_pack(tmp_path / "pack", [record])

    with pytest.raises(PackValidationError, match="must be safety reviewed"):
        validate_character_pack(pack_dir)


def test_character_pack_rejects_eval_reference_to_unknown_record(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    (pack_dir / "evaluation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "bad-eval",
                        "query": "你好",
                        "expected_record_ids": ["missing-record"],
                        "top_k": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PackValidationError, match="unknown records"):
        validate_character_pack(pack_dir)


def test_repository_demo_pack_is_valid_and_original() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pack = validate_character_pack(project_root / "packs" / "demo")

    assert pack.manifest.pack_id == "mira-demo"
    assert pack.manifest.provenance.license == "CC0-1.0"
    assert len(pack.records) == 10
    assert len(pack.evaluation.cases) == 6


def test_artifact_manifest_detects_tampering(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")
    context, stage, _ = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        verify_artifact_directory(stage)
        (stage / "index.bin").write_bytes(b"tampered")
        with pytest.raises(ArtifactValidationError, match="integrity"):
            verify_artifact_directory(stage)
    finally:
        context.__exit__(None, None, None)


def test_artifact_store_publishes_immutable_version_and_resolves_current(
    tmp_path: Path,
) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")
    context, stage, manifest = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        published = store.publish(stage)
    finally:
        context.__exit__(None, None, None)

    current = store.resolve_current("demo-companion")
    assert current.path == published.path
    assert current.manifest.artifact_hash == manifest.artifact_hash
    assert current.manifest.embedding_model == "example/embedding-v1"
    assert current.manifest.vector_dimension == 8
    assert current.manifest.provenance.license == "CC0-1.0"
    assert (current.path / ARTIFACT_MANIFEST_FILENAME).is_file()


def test_failed_stage_does_not_replace_current_artifact(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")
    context, stage, first_manifest = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        first = store.publish(stage)
    finally:
        context.__exit__(None, None, None)

    with pytest.raises(RuntimeError, match="build failed"):
        with store.stage("demo-companion") as failed_stage:
            (failed_stage / "partial.bin").write_bytes(b"partial")
            raise RuntimeError("build failed")

    current = store.resolve_current("demo-companion")
    assert current.path == first.path
    assert current.manifest.artifact_hash == first_manifest.artifact_hash


def test_second_publish_atomically_switches_pointer_and_keeps_old_version(
    tmp_path: Path,
) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")

    first_context, first_stage, _ = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        first = store.publish(first_stage)
    finally:
        first_context.__exit__(None, None, None)

    second_context, second_stage, second_manifest = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.1.0",
        content=b"index-v2",
    )
    try:
        second = store.publish(second_stage)
    finally:
        second_context.__exit__(None, None, None)

    current = store.resolve_current("demo-companion")
    assert current.path == second.path
    assert current.manifest.artifact_hash == second_manifest.artifact_hash
    assert first.path.is_dir()
    assert first.path != second.path


def test_resolve_missing_artifact_store_is_strictly_read_only(tmp_path: Path) -> None:
    store_root = tmp_path / "missing-store"
    store = ArtifactStore(store_root)

    with pytest.raises(ArtifactValidationError, match="does not exist"):
        store.resolve_current("demo-companion")

    assert not store_root.exists()


def test_resolve_current_fails_closed_on_published_file_tampering(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")
    context, stage, _ = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        published = store.publish(stage)
    finally:
        context.__exit__(None, None, None)
    (published.path / "index.bin").write_bytes(b"tampered")

    with pytest.raises(ArtifactValidationError, match="integrity"):
        store.resolve_current("demo-companion")


def test_resolve_current_fails_closed_on_extra_file(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store = ArtifactStore(tmp_path / "artifacts")
    context, stage, _ = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        published = store.publish(stage)
    finally:
        context.__exit__(None, None, None)
    (published.path / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="file set mismatch"):
        store.resolve_current("demo-companion")


def test_resolve_current_fails_closed_on_corrupt_pointer(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path / "pack")
    store_root = tmp_path / "artifacts"
    store = ArtifactStore(store_root)
    context, stage, _ = _stage_artifact(
        store,
        pack_dir,
        artifact_version="1.0.0",
        content=b"index-v1",
    )
    try:
        store.publish(stage)
    finally:
        context.__exit__(None, None, None)
    (store_root / "demo-companion" / "current.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="Unable to load artifact metadata"):
        store.resolve_current("demo-companion")
