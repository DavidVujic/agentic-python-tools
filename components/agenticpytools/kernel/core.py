import time
from pathlib import Path

from agenticpytools.environment import is_windows
from jupyter_core.paths import jupyter_runtime_dir
from jupyter_client import BlockingKernelClient
import json



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


def in_runtime_dir(connection_file: str) -> bool:
    """True if the connection file lives in the Jupyter runtime dir."""
    cf = Path(connection_file).expanduser().resolve()
    rt = Path(jupyter_runtime_dir()).resolve()

    return cf.parent == rt


def is_running_stored(stored: dict, timeout: int = 30) -> bool:
    """Probe a kernel described by persisted state (connection file path)."""
    connection_file = stored["connection_file"]
    if not in_runtime_dir(connection_file):
        return False

    kc = BlockingKernelClient()

    try:
        kc.load_connection_file(connection_file)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return False

    kc.start_channels()

    try:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if kc.is_alive():
                return True

            time.sleep(0.1)

        return False
    finally:
        kc.stop_channels()

