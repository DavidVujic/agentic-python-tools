from pathlib import Path

from agenticpytools import storage
from agenticpytools.kernel import (
    create_and_start_kernel,
    get_kernel_name,
    is_running_stored,
    shutdown_adopted,
)
from jupyter_client import BlockingKernelClient


def create(project: Path, timeout: int) -> BlockingKernelClient:
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    freshly_started = not (stored and is_running_stored(stored, timeout))

    if freshly_started:
        if stored and not is_running_stored(stored, timeout):
            shutdown_adopted(stored["connection_file"])

        km = create_and_start_kernel(project)
        kc = km.client()
        storage.save_entry(kernel_name, str(km.connection_file), project.as_posix())
    else:
        try:
            kc = BlockingKernelClient()
            kc.load_connection_file(stored["connection_file"])
            kc.start_channels()
            kc.wait_for_ready(timeout=timeout)
        except (FileNotFoundError, RuntimeError) as e:
            kc.stop_channels()
            raise RuntimeError(f"Failed to connect to external kernel: {e}")

    return kc


def close(project: Path, timeout: int) -> None:
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    if not stored or not is_running_stored(stored, timeout):
        print("not running")
        return

    kc = stored.get("client")
    if kc is not None:
        kc.stop_channels()

    shutdown_adopted(stored["connection_file"])
