"""Unified launcher for local web and Telegram runtime modes."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

from src.adapters.telegram import main as telegram_main
from src.core.config import PROJECT_ROOT, settings


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Unified runtime launcher for NeneBot.",
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
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def ensure_ollama_runtime(children: list[subprocess.Popen[object]]) -> None:
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


def terminate_processes(children: Sequence[subprocess.Popen[object]]) -> None:
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

    children: list[subprocess.Popen[object]] = []
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
                    f"http://{args.host}:{args.port}/health/live", timeout=1
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

        print("NeneBot dev mode is running.")
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


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for the unified launcher."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
