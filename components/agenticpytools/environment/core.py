import os
import shutil
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def windows_venv(venv_dir: Path) -> Path:
    return venv_dir / "Scripts" / "python.exe"


def expected_venv_python(venv_dir: Path) -> Path:
    return windows_venv(venv_dir) if is_windows() else venv_dir / "bin" / "python"


def venv_dir(project: str | Path) -> Path:
    """The project's virtual environment directory."""
    return Path(project) / ".venv"


def venv_python(project_path: str | Path) -> Path:
    """Find the Python interpreter of the project's venv."""
    project = Path(project_path).expanduser().resolve()

    venv = venv_dir(project)
    venv_python_candidate = expected_venv_python(venv)

    if venv_python_candidate.exists():
        return venv_python_candidate

    raise FileNotFoundError(f"No virtual environment found in {project}")


def is_uv(project: Path) -> bool:
    has_uv = shutil.which("uv") is not None
    lock_file = project / "uv.lock"

    return has_uv and lock_file.exists()
