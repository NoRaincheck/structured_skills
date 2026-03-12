from __future__ import annotations

from pathlib import Path

from structured_skills.main import _parse_args, main
from structured_skills.server import create_mcp_server

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_parse_args_supports_mcp_command() -> None:
    args = _parse_args([str(FIXTURES), "mcp", "--server-name", "custom-structured_skills"])
    assert args.skills_dir == str(FIXTURES)
    assert args.command == "mcp"
    assert args.server_name == "custom-structured_skills"


def test_create_mcp_server_exposes_run_method() -> None:
    server = create_mcp_server(FIXTURES, server_name="structured_skills-test")
    assert callable(server.run)


def test_main_mcp_invokes_server_run(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class DummyServer:
        def run(self) -> None:
            calls["ran"] = True

    def _fake_create_mcp_server(
        skill_root_dir: Path, server_name: str = "structured_skills"
    ) -> DummyServer:
        calls["skill_root_dir"] = skill_root_dir
        calls["server_name"] = server_name
        return DummyServer()

    monkeypatch.setattr("structured_skills.main.create_mcp_server", _fake_create_mcp_server)
    exit_code = main([str(FIXTURES), "mcp", "--server-name", "cli-structured_skills"])
    assert exit_code == 0
    assert calls["skill_root_dir"] == FIXTURES
    assert calls["server_name"] == "cli-structured_skills"
    assert calls["ran"] is True


def test_execute_supports_inferred_flag_args_for_cli_targets(capsys) -> None:
    exit_code = main(
        [
            "example/",
            "execute",
            "ttrpg-engine",
            "random-event",
            "--seed",
            "7",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "action_focus" in output
    assert "topic_focus" in output


def test_execute_function_target_without_args_still_works(capsys) -> None:
    exit_code = main(["example/", "execute", "ttrpg-engine", "d6"])
    assert exit_code == 0
    output = capsys.readouterr().out.strip()
    assert output.isdigit()
    assert 1 <= int(output) <= 6
