import os
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def windows_venv(venv_dir: Path) -> Path:
    return venv_dir / "Scripts" / "python.exe"


def venv_path(venv_dir: Path) -> Path:
    return windows_venv(venv_dir) if is_windows() else venv_dir / "bin" / "python"


def venv_python(project_path: str | Path) -> Path:
    """Find the Python interpreter of the project's venv."""
    project = Path(project_path).expanduser().resolve()

    candidates = [project / ".venv"]

    for venv_dir in candidates:
        exe = venv_path(venv_dir)

        if exe.exists():
            return exe

    raise FileNotFoundError(f"No virtual environment found in {project}")
