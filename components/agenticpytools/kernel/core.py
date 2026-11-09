import hashlib
import importlib.metadata
from pathlib import Path

from agenticpytools.environment import is_uv, is_windows, venv_dir, venv_python
from jupyter_core.paths import jupyter_runtime_dir

KERNEL_NAME_PREFIX = "agenticpytools"


def get_kernel_name(project: Path) -> str:
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:8]
    return f"{KERNEL_NAME_PREFIX}-{project.name}-{digest}"


def get_session_kernel_name(project: Path, session_id: str) -> str:
    """Registry key of a session's kernel in a project."""
    if not session_id.strip():
        raise ValueError("session_id must be a non-empty string")

    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]

    return f"{get_kernel_name(project)}-{digest}"


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
    """Check the project venv's site-packages for an ipykernel distribution."""
    venv = venv_dir(project)

    if not venv.is_dir():
        return False

    lib = next((d for d in venv.iterdir() if d.name.lower() == "lib"), None)

    if lib is None:
        return False

    site_packages = [*lib.glob("*/site-packages"), lib / "site-packages"]

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
            f"ipykernel is not installed in the project venv at {venv_dir(project)}; "
            "add it to the project dependencies"
        )

    return [str(venv_python(project))] + basics
