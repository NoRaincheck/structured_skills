import subprocess
import sys


class TestCLI:
    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "structured_skills", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "structured_skills" in result.stdout.lower()

    def test_no_command_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "structured_skills"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Available commands" in result.stdout or "usage:" in result.stdout.lower()

    def test_run_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "structured_skills", "run", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "skill" in result.stdout.lower()

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "structured_skills", "cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_check_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "structured_skills", "check", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "fix" in result.stdout.lower()
