from pathlib import Path

from agenticpytools import storage
from agenticpytools.kernel.close import shutdown_adopted
from agenticpytools.kernel.core import get_kernel_name
from agenticpytools.kernel.create import create_and_start_kernel
from jupyter_client import BlockingKernelClient


def _connect_new_kernel(project: Path, timeout: int) -> BlockingKernelClient:
    km = create_and_start_kernel(project)
    kc = km.client()

    try:
        kc.start_channels()
        kc.wait_for_ready(timeout=timeout)

        if not kc.is_alive():
            raise RuntimeError("Failed to create or connect to kernel.")
    except Exception:
        kc.stop_channels()
        km.shutdown_kernel(now=True)
        raise

    return kc


def create(path: str, timeout: int) -> BlockingKernelClient:
    project = Path(path).expanduser().resolve()
    kernel_name = get_kernel_name(project)

    stored = storage.load_entry(kernel_name)

    if stored:
        try:
            kc = BlockingKernelClient()
            kc.load_connection_file(stored["connection_file"])
            kc.start_channels()
            kc.wait_for_ready(timeout=timeout)

            if kc.is_alive():
                return kc
            else:
                shutdown_adopted(stored["connection_file"])
                storage.delete_entry(kernel_name)
        except (FileNotFoundError, RuntimeError):
            shutdown_adopted(stored["connection_file"])
            storage.delete_entry(kernel_name)

    kc = _connect_new_kernel(project, timeout)
    storage.save_entry(kernel_name, str(kc.connection_file), path)

    return kc


def close(project: Path) -> None:
    kernel_name = get_kernel_name(project)

    stored = storage.load_entry(kernel_name)

    if not stored:
        print("not running")
        return

    shutdown_adopted(stored["connection_file"])
    storage.delete_entry(kernel_name)
