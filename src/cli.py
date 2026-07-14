"""Unified launcher for local web and Telegram runtime modes."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from src.adapters.telegram import main as telegram_main
from src.core.config import PROJECT_ROOT, settings

if TYPE_CHECKING:
    from src.services.embedding_svc import EmbeddingService

DEFAULT_PACK_PATH = PROJECT_ROOT / "packs" / "demo"
DEFAULT_ARTIFACT_STORE = PROJECT_ROOT / "artifacts"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Persona Studio runtime and offline Character Pack tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    local_parser = subparsers.add_parser(
        "local",
        aliases=["web"],
        help="Run the FastAPI backend locally.",
    )
    local_parser.add_argument("--host", default=settings.host)
    local_parser.add_argument("--port", type=int, default=settings.port)
    local_parser.add_argument("--reload", action="store_true")
    local_parser.set_defaults(handler=run_local)

    telegram_parser = subparsers.add_parser(
        "telegram",
        help="Run the Telegram adapter in polling mode.",
    )
    telegram_parser.set_defaults(handler=run_telegram)

    dev_parser = subparsers.add_parser(
        "dev",
        help="Run backend and frontend together for local development.",
    )
    dev_parser.add_argument("--host", default=settings.host)
    dev_parser.add_argument("--port", type=int, default=settings.port)
    dev_parser.add_argument("--frontend-port", type=int, default=5173)
    dev_parser.add_argument("--skip-ollama-check", action="store_true")
    dev_parser.add_argument(
        "--boot-timeout",
        type=int,
        default=120,
        help="Seconds to wait for backend health endpoint (first run may need 1–2 min).",
    )
    dev_parser.set_defaults(handler=run_dev)

    pack_parser = subparsers.add_parser(
        "pack",
        help="Validate, build, evaluate, promote, or roll back Character Packs.",
    )
    pack_commands = pack_parser.add_subparsers(dest="pack_command", required=True)

    validate_parser = pack_commands.add_parser("validate", help="Validate every Pack input.")
    validate_parser.add_argument("pack_dir", nargs="?", default=str(DEFAULT_PACK_PATH))
    validate_parser.set_defaults(handler=run_pack_validate)

    build_pack_parser = pack_commands.add_parser(
        "build",
        help="Build and install an immutable artifact without activating it.",
    )
    build_pack_parser.add_argument("pack_dir", nargs="?", default=str(DEFAULT_PACK_PATH))
    build_pack_parser.add_argument("--store", default=str(DEFAULT_ARTIFACT_STORE))
    build_pack_parser.add_argument("--artifact-version")
    build_pack_parser.set_defaults(handler=run_pack_build)

    eval_parser = pack_commands.add_parser(
        "eval",
        help="Evaluate the active artifact against its Pack retrieval cases.",
    )
    eval_parser.add_argument("pack_dir", nargs="?", default=str(DEFAULT_PACK_PATH))
    eval_parser.add_argument("--store", default=str(DEFAULT_ARTIFACT_STORE))
    eval_parser.set_defaults(handler=run_pack_eval)

    promote_parser = pack_commands.add_parser(
        "promote",
        help="Atomically activate an installed artifact.",
    )
    promote_parser.add_argument("pack_id")
    promote_parser.add_argument("reference", help="Full hash, exact version, or directory name.")
    promote_parser.add_argument("--store", default=str(DEFAULT_ARTIFACT_STORE))
    promote_parser.set_defaults(handler=run_pack_promote)

    rollback_parser = pack_commands.add_parser(
        "rollback",
        help="Atomically reactivate the previous artifact.",
    )
    rollback_parser.add_argument("pack_id")
    rollback_parser.add_argument("--store", default=str(DEFAULT_ARTIFACT_STORE))
    rollback_parser.set_defaults(handler=run_pack_rollback)

    derive_parser = pack_commands.add_parser(
        "derive",
        help="Create a new Pack version with exact provenance sources removed.",
    )
    derive_parser.add_argument("pack_dir")
    derive_parser.add_argument("--output", required=True)
    derive_parser.add_argument("--version", required=True)
    derive_parser.add_argument(
        "--exclude-source",
        action="append",
        required=True,
        help="Exact provenance.source value to remove; repeat for multiple sources.",
    )
    derive_parser.set_defaults(handler=run_pack_derive)

    return parser


def build_backend_command(*, host: str, port: int, reload: bool) -> list[str]:
    """Build the uvicorn command used by the development launcher."""
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


def choose_frontend_command(frontend_dir: Path, *, port: int) -> list[str]:
    """Pick the frontend package manager command based on lockfiles."""
    if (frontend_dir / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (frontend_dir / "yarn.lock").exists():
        package_manager = "yarn"
    else:
        package_manager = "npm"

    return [
        package_manager,
        "run",
        "dev",
        "--",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]


def ollama_is_reachable(base_url: str) -> bool:
    """Return whether the Ollama HTTP API is reachable."""
    tags_url = base_url.rstrip("/") + "/api/tags"
    request = urllib.request.Request(tags_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return bool(200 <= response.status < 500)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def ensure_ollama_runtime(children: list[subprocess.Popen[bytes]]) -> None:
    """Start a local Ollama daemon if the current provider needs it."""
    if settings.llm_provider != "ollama":
        return

    if ollama_is_reachable(settings.ollama_base_url):
        return

    if shutil.which("ollama") is None:
        raise RuntimeError(
            "LLM_PROVIDER=ollama but the `ollama` command was not found. "
            "Install Ollama or switch to another provider."
        )

    process = subprocess.Popen(
        ["ollama", "serve"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    children.append(process)

    for _ in range(10):
        if ollama_is_reachable(settings.ollama_base_url):
            return
        time.sleep(1)

    raise RuntimeError("Started `ollama serve`, but the Ollama API is still unreachable.")


def terminate_processes(children: Sequence[subprocess.Popen[bytes]]) -> None:
    """Terminate child processes started by the launcher."""
    for process in reversed(children):
        if process.poll() is not None:
            continue
        process.terminate()

    deadline = time.time() + 5
    for process in reversed(children):
        if process.poll() is not None:
            continue
        timeout = max(deadline - time.time(), 0.1)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()


def run_local(args: argparse.Namespace) -> int:
    """Run the FastAPI backend only."""
    import uvicorn

    uvicorn.run("src.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def run_telegram(_: argparse.Namespace) -> int:
    """Run the Telegram polling adapter."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to launch Telegram mode.")
    asyncio.run(telegram_main())
    return 0


def run_dev(args: argparse.Namespace) -> int:
    """Run backend and frontend together for local development."""
    frontend_dir = PROJECT_ROOT / "frontend"
    if not frontend_dir.exists():
        raise RuntimeError(f"Frontend directory not found: {frontend_dir}")

    children: list[subprocess.Popen[bytes]] = []
    try:
        if not args.skip_ollama_check:
            ensure_ollama_runtime(children)

        backend = subprocess.Popen(
            build_backend_command(host=args.host, port=args.port, reload=True),
            cwd=str(PROJECT_ROOT),
        )
        children.append(backend)

        # Start the frontend immediately — it can connect once the backend is ready.
        frontend = subprocess.Popen(
            choose_frontend_command(frontend_dir, port=args.frontend_port),
            cwd=str(frontend_dir),
        )
        children.append(frontend)

        # Poll the health endpoint; first-run vector index build may take 1–2 minutes.
        deadline = time.time() + args.boot_timeout
        backend_ready = False
        while time.time() < deadline:
            if backend.poll() is not None:
                return int(backend.returncode or 1)
            try:
                with urllib.request.urlopen(
                    f"http://{args.host}:{args.port}/livez", timeout=1
                ) as resp:
                    if 200 <= resp.status < 500:
                        backend_ready = True
                        break
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
            time.sleep(0.5)

        if not backend_ready:
            print(f"Backend failed to start within {args.boot_timeout} seconds.")
            return 1

        print("Persona Studio dev mode is running.")
        print(f"Frontend: http://localhost:{args.frontend_port}")
        print(f"Backend : http://localhost:{args.port}")
        print("Press Ctrl+C to stop.")

        while True:
            for process in (backend, frontend):
                if process.poll() is not None:
                    return int(process.returncode or 0)
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        terminate_processes(children)


def _embedding_service() -> EmbeddingService:
    from src.services.embedding_svc import EmbeddingService

    return EmbeddingService()


def run_pack_validate(args: argparse.Namespace) -> int:
    """Validate an authored Character Pack without building an index."""
    from src.knowledge.pack import validate_character_pack

    pack = validate_character_pack(args.pack_dir)
    print(
        json.dumps(
            {
                "pack_id": pack.manifest.pack_id,
                "version": pack.manifest.version,
                "records": len(pack.records),
                "evaluation_cases": len(pack.evaluation.cases),
                "content_hash": pack.content_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_pack_build(args: argparse.Namespace) -> int:
    """Build and install an immutable artifact without changing current."""
    from src.knowledge.builder import build_pack_artifact

    published = build_pack_artifact(
        args.pack_dir,
        args.store,
        _embedding_service(),
        artifact_version=args.artifact_version,
        activate=False,
    )
    print(
        json.dumps(
            {
                "pack_id": published.manifest.pack_id,
                "artifact_version": published.manifest.artifact_version,
                "artifact_hash": published.manifest.artifact_hash,
                "path": str(published.path),
                "active": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_pack_eval(args: argparse.Namespace) -> int:
    """Evaluate the active artifact with versioned Pack fixtures."""
    from src.knowledge.artifacts import ArtifactStore
    from src.knowledge.builder import evaluate_loaded_artifact, load_artifact
    from src.knowledge.pack import validate_character_pack

    pack = validate_character_pack(args.pack_dir)
    published = ArtifactStore(args.store).resolve_current(pack.manifest.pack_id)
    report = evaluate_loaded_artifact(
        load_artifact(published), pack.evaluation, _embedding_service()
    )
    print(
        json.dumps(
            {
                "pack_id": report.pack_id,
                "artifact_hash": report.artifact_hash,
                "passed": report.passed,
                "results": [
                    {
                        "case_id": result.case_id,
                        "passed": result.passed,
                        "expected": result.expected_record_ids,
                        "retrieved": result.retrieved_record_ids,
                    }
                    for result in report.results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report.passed else 1


def run_pack_promote(args: argparse.Namespace) -> int:
    """Atomically activate an installed artifact."""
    from src.knowledge.artifacts import ArtifactStore

    published = ArtifactStore(args.store).activate(args.pack_id, args.reference)
    print(
        json.dumps(
            {
                "pack_id": published.manifest.pack_id,
                "artifact_version": published.manifest.artifact_version,
                "artifact_hash": published.manifest.artifact_hash,
                "active": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_pack_rollback(args: argparse.Namespace) -> int:
    """Activate the artifact preceding current."""
    from src.knowledge.artifacts import ArtifactStore

    published = ArtifactStore(args.store).rollback(args.pack_id)
    print(
        json.dumps(
            {
                "pack_id": published.manifest.pack_id,
                "artifact_version": published.manifest.artifact_version,
                "artifact_hash": published.manifest.artifact_hash,
                "rolled_back": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_pack_derive(args: argparse.Namespace) -> int:
    """Create a validated new Pack version with selected sources removed."""
    from src.knowledge.editor import derive_pack_without_sources

    report = derive_pack_without_sources(
        args.pack_dir,
        args.output,
        version=args.version,
        excluded_sources=set(args.exclude_source),
    )
    print(
        json.dumps(
            {
                "pack_id": report.pack.manifest.pack_id,
                "version": report.pack.manifest.version,
                "content_hash": report.pack.content_hash,
                "output": str(report.pack.root),
                "excluded_sources": report.excluded_sources,
                "removed_record_ids": report.removed_record_ids,
                "removed_evaluation_case_ids": report.removed_evaluation_case_ids,
                "remaining_records": len(report.pack.records),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for the unified launcher."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
