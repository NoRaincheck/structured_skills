import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def platformdir_env_override(data_dir: Path):
    """Context manager to temporarily override platformdirs environment variables."""
    overrides = _get_platformdir_env_overrides(data_dir)
    old_values = {}
    for key, value in overrides.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = value
        print(key, value)
    try:
        yield
    finally:
        for key, old_value in old_values.items():
            if old_value is None:
                del os.environ[key]
            else:
                os.environ[key] = old_value


def _get_platformdir_env_overrides(data_dir: Path) -> dict[str, str]:
    """Get environment variables to override platformdirs paths."""
    overrides: dict[str, str] = {}

    if sys.platform == "win32":
        overrides["WIN_PD_OVERRIDE_USER_DATA"] = str(data_dir)
    else:
        overrides["XDG_DATA_HOME"] = str(data_dir)

    return overrides
