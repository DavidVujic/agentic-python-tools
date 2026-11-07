import hashlib
import importlib.metadata
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


def venv_has_ipykernel(project: Path) -> bool:
    """Check the project venv's site-packages for an ipykernel distribution (no subprocess)."""
    venv = project / ".venv"
    site_packages = [
        *((venv / "lib").glob("python*/site-packages")),
        venv / "Lib" / "site-packages",  # windows layout
    ]

    return any(
        (dist.metadata["Name"] or "").lower() == "ipykernel"
        for sp in site_packages
        if sp.is_dir()
        for dist in importlib.metadata.distributions(path=[str(sp)])
    )


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

    if not venv_has_ipykernel(project):
        raise RuntimeError(
            f"ipykernel is not installed in the project venv at {project / '.venv'}; "
            "add it to the project dependencies"
        )

    return [str(venv_python(project))] + basics
