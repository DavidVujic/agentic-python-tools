import hashlib
from pathlib import Path

from agenticpytools.environment import is_uv, is_windows, venv_python
from jupyter_core.paths import jupyter_runtime_dir


def get_kernel_name(project: Path) -> str:
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:8]
    return f"repl-{project.name}-{digest}"


def get_connection_file_path(kernel_id: str) -> Path:
    runtime_dir = Path(jupyter_runtime_dir())

    return runtime_dir / f"kernel-{kernel_id}.json"


def get_transport() -> str:
    return "tcp" if is_windows() else "ipc"


def spec_data(argv: list[str], kernel_name: str) -> dict:
    return {
        "argv": argv,
        "display_name": f"Python REPL ({kernel_name})",
        "language": "python",
    }


def kernel_argv(project: Path) -> list[str]:
    """Kernel argv, based on what's used in the project."""
    basics = ["-m", "ipykernel_launcher", "-f", "{connection_file}"]

    if is_uv(project):
        return [
            "uv",
            "run",
            "--project",
            str(project),
            "--with",
            "ipykernel",
            "python",
        ] + basics

    return [str(venv_python(project))] + basics
