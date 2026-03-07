import json
import subprocess
import sys


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "structured_skills", *args],
        capture_output=True,
        text=True,
    )


def test_tasks_help():
    result = _run_cli("tasks", "--help")
    assert result.returncode == 0
    assert "Task commands" in result.stdout


def test_tasks_crud_flow(tmp_path):
    working_dir = str(tmp_path / "session")

    create_result = _run_cli(
        "tasks",
        "--working-dir",
        working_dir,
        "create",
        "Run scheduler checks",
        "--meta",
        "source=cli-test",
        "--json",
    )
    assert create_result.returncode == 0
    created = json.loads(create_result.stdout)
    task_id = created["id"]
    assert task_id.startswith("run-scheduler-checks-")

    list_result = _run_cli("tasks", "--working-dir", working_dir, "list", "--json")
    assert list_result.returncode == 0
    tasks = json.loads(list_result.stdout)
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id
    assert tasks[0]["status"] == "open"

    start_result = _run_cli("tasks", "--working-dir", working_dir, "start", task_id)
    assert start_result.returncode == 0
    assert "in_progress" in start_result.stdout

    fail_result = _run_cli(
        "tasks",
        "--working-dir",
        working_dir,
        "fail",
        task_id,
        "--error",
        "upstream timed out",
    )
    assert fail_result.returncode == 0
    assert "failed" in fail_result.stdout

    reopen_result = _run_cli("tasks", "--working-dir", working_dir, "reopen", task_id)
    assert reopen_result.returncode == 0
    assert "open" in reopen_result.stdout

    complete_result = _run_cli(
        "tasks",
        "--working-dir",
        working_dir,
        "complete",
        task_id,
        "--note",
        "completed after retry",
    )
    assert complete_result.returncode == 0
    assert "done" in complete_result.stdout

    show_result = _run_cli("tasks", "--working-dir", working_dir, "show", task_id, "--json")
    assert show_result.returncode == 0
    shown = json.loads(show_result.stdout)
    assert shown["status"] == "done"
    assert shown["last_note"] == "completed after retry"
