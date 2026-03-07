import importlib.util
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

MEMORY_SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "memory" / "scripts" / "memory.py"


def _load_memory_module():
    module_name = f"memory_skill_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MEMORY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_add_memory_updates_skill_and_reset_clears_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = _load_memory_module()

    memory.add_memory("Dark mode preferred", "user")
    assert (tmp_path / "memory.txt").read_text().startswith("[user] Dark mode preferred")
    assert "## Memories" in (tmp_path / "SKILL.md").read_text()

    memory.reset()
    assert (tmp_path / "memory.txt").read_text() == ""
    assert (tmp_path / "history.txt").read_text() == ""


def test_memory_window_inserts_single_warning_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory = _load_memory_module()

    for idx in range(50):
        memory.add_memory(f"memory {idx}")

    memory_lines = (tmp_path / "memory.txt").read_text().splitlines()
    assert memory_lines[0] == "_comment:FULL PLEASE CONSOLIDATE"
    assert memory_lines.count("_comment:FULL PLEASE CONSOLIDATE") == 1

    memory.add_memory("memory 50")
    memory_lines = (tmp_path / "memory.txt").read_text().splitlines()
    assert memory_lines.count("_comment:FULL PLEASE CONSOLIDATE") == 1


def test_search_memory_cli_prints_full_line_results(tmp_path):
    subprocess.run(
        [sys.executable, str(MEMORY_SCRIPT), "add_memory", "dark mode", "--group", "user"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [sys.executable, str(MEMORY_SCRIPT), "search_memory", "dark", "--group", "user"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "[user] dark mode"
