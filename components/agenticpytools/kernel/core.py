from pathlib import Path

from agenticpytools.environment import is_windows
from jupyter_core.paths import jupyter_runtime_dir


def get_kernel_name(project_name: str) -> str:
    return f"repl-{project_name}"


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
