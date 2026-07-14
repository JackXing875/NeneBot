from src.cli import build_backend_command, build_parser, choose_frontend_command, main


def test_build_backend_command_supports_reload_flag() -> None:
    command = build_backend_command(host="127.0.0.1", port=8010, reload=True)

    assert command[-1] == "--reload"
    assert "src.main:app" in command
    assert "8010" in command


def test_choose_frontend_command_defaults_to_npm_without_lockfile(tmp_path) -> None:  # type: ignore[no-untyped-def]
    command = choose_frontend_command(tmp_path, port=5179)

    assert command[:3] == ["npm", "run", "dev"]
    assert command[-1] == "5179"


def test_choose_frontend_command_prefers_pnpm_when_lockfile_exists(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")

    command = choose_frontend_command(tmp_path, port=5173)

    assert command[0] == "pnpm"


def test_cli_parser_accepts_telegram_subcommand() -> None:
    parser = build_parser()

    args = parser.parse_args(["telegram"])

    assert args.command == "telegram"


def test_cli_parser_accepts_pack_workflow() -> None:
    parser = build_parser()

    args = parser.parse_args(["pack", "promote", "mira-demo", "1.0.0", "--store", "/tmp/artifacts"])

    assert args.command == "pack"
    assert args.pack_command == "promote"
    assert args.pack_id == "mira-demo"
    assert args.reference == "1.0.0"


def test_pack_validate_command_checks_repository_demo(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(["pack", "validate", "packs/demo"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"pack_id": "mira-demo"' in output
    assert '"records": 10' in output


def test_cli_parser_accepts_source_removal_derivation() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "pack",
            "derive",
            "packs/demo",
            "--output",
            "/tmp/demo-next",
            "--version",
            "1.1.0",
            "--exclude-source",
            "retired-source",
        ]
    )

    assert args.pack_command == "derive"
    assert args.exclude_source == ["retired-source"]
