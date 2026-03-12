from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_cmd(args: list[str]) -> str:
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = src_path if not pythonpath else f"{src_path}{os.pathsep}{pythonpath}"
    completed = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_package_cli_execute_random_event_passthrough() -> None:
    structured_skills_exe = shutil.which("structured_skills")
    assert structured_skills_exe is not None
    output = _run_cmd(
        [
            structured_skills_exe,
            "example/",
            "execute",
            "ttrpg-engine",
            "random-event",
            "--seed",
            "7",
        ]
    )
    payload = json.loads(output)
    assert "action_focus" in payload
    assert "topic_focus" in payload


def test_package_cli_execute_d6_without_args() -> None:
    structured_skills_exe = shutil.which("structured_skills")
    assert structured_skills_exe is not None
    output = _run_cmd(
        [
            structured_skills_exe,
            "example/",
            "execute",
            "ttrpg-engine",
            "d6",
        ]
    )
    value = int(output.strip())
    assert 1 <= value <= 6


def test_single_file_cli_execute_random_event_passthrough() -> None:
    output = _run_cmd(
        [
            sys.executable,
            "structured_skills.py",
            "example/",
            "execute",
            "ttrpg-engine",
            "random-event",
            "--seed",
            "7",
        ]
    )
    payload = json.loads(output)
    assert "action_focus" in payload
    assert "topic_focus" in payload


def test_single_file_cli_execute_d6_without_args() -> None:
    output = _run_cmd(
        [
            sys.executable,
            "structured_skills.py",
            "example/",
            "execute",
            "ttrpg-engine",
            "d6",
        ]
    )
    value = int(output.strip())
    assert 1 <= value <= 6
