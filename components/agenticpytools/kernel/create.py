import json
import tempfile
import uuid
from pathlib import Path

from agenticpytools.environment import venv_python
from agenticpytools.kernel.core import (
    get_connection_file_path,
    get_kernel_name,
    get_transport,
    spec_data,
)
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager


def create_kernel_manager(
    kernel_name: str, connection_file: str, **_kwargs
) -> KernelManager:
    transport = get_transport()

    return KernelManager(
        kernel_name=kernel_name, connection_file=connection_file, transport=transport
    )


def installed_argv(ksm: KernelSpecManager, kernel_name: str) -> list[str] | None:
    """Return the argv of the installed kernelspec, or None if not installed."""
    installed = ksm.get_all_specs().get(kernel_name, {})

    return installed.get("spec", {}).get("argv")


def ensure_project_spec(kernel_name: str, current_python: str) -> None:
    """Install a kernelspec pointing at the project's venv, unless it already does."""
    argv = [
        current_python,
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]

    ksm = KernelSpecManager()

    if installed_argv(ksm, kernel_name) == argv:
        return

    with tempfile.TemporaryDirectory() as tmp:
        spec_dir = Path(tmp) / kernel_name
        spec_dir.mkdir()

        data = spec_data(argv, kernel_name)
        spec_path = spec_dir / "kernel.json"
        spec_path.write_text(json.dumps(data))

        ksm.install_kernel_spec(str(spec_dir), kernel_name=kernel_name, user=True)


def create_and_start_kernel(project: Path) -> KernelManager:
    kernel_name = get_kernel_name(project)
    current_python = str(venv_python(project))

    ensure_project_spec(kernel_name, current_python)
    transport = get_transport()

    kernel_id = str(uuid.uuid4())
    connection_file = str(get_connection_file_path(kernel_id))  # ← back!

    km = KernelManager(
        kernel_name=kernel_name, connection_file=connection_file, transport=transport
    )

    try:
        km.start_kernel()
    except Exception:
        km.shutdown_kernel(now=True)
        raise

    return km
