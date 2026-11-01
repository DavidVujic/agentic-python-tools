from pathlib import Path

from agenticpytools import storage
from agenticpytools.kernel.close import shutdown_adopted
from agenticpytools.kernel.core import get_kernel_name
from agenticpytools.kernel.create import create_and_start_kernel
from jupyter_client import BlockingKernelClient


def create(path: str, timeout: int) -> BlockingKernelClient:
    project = Path(path).expanduser().resolve()
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    if stored:
        try:
            kc = BlockingKernelClient()
            kc.load_connection_file(stored["connection_file"])
            kc.start_channels()
            kc.wait_for_ready(timeout=timeout)

            return kc
        except (FileNotFoundError, RuntimeError):
            shutdown_adopted(stored["connection_file"])
            storage.delete_entry(kernel_name)

    km = create_and_start_kernel(project)
    kc = km.client()

    storage.save_entry(kernel_name, str(km.connection_file), path)

    return kc


"""

    if stored and not is_running_stored(stored, timeout):
        shutdown_adopted(stored["connection_file"])
        storage.delete_entry(kernel_name)
        stored = None

    if not stored:
        km = create_and_start_kernel(project)
        kc = km.client()
        storage.save_entry(kernel_name, str(km.connection_file), path)

        return kc

    try:
        kc = BlockingKernelClient()
        kc.load_connection_file(stored["connection_file"])
        kc.start_channels()
        kc.wait_for_ready(timeout=timeout)
    except (FileNotFoundError, RuntimeError) as e:
        storage.delete_entry(kernel_name)
        kc.stop_channels()
        raise RuntimeError(f"Failed to connect: {e}")

    return kc
"""


def close(project: Path) -> None:
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    if not stored:
        print("not running")
        return

    shutdown_adopted(stored["connection_file"])
    storage.delete_entry(kernel_name)
