import sqlite3
from pathlib import Path

from agenticpytools import storage
from agenticpytools.kernel.close import shutdown_adopted
from agenticpytools.kernel.core import get_session_kernel_name
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


def _reconnect(
    kernel_name: str, stored: dict, timeout: int, conn: sqlite3.Connection
) -> BlockingKernelClient | None:
    """Connect to the stored kernel, or shut it down and unregister it."""
    try:
        kc = BlockingKernelClient()
        kc.load_connection_file(stored["connection_file"])
        kc.start_channels()
        kc.wait_for_ready(timeout=timeout)

        if kc.is_alive():
            return kc

        kc.stop_channels()
    except (FileNotFoundError, RuntimeError):
        kc.stop_channels()

    shutdown_adopted(stored["connection_file"])
    storage.delete_entry(kernel_name, conn=conn)

    return None


def create(path: str, session_id: str, timeout: int) -> BlockingKernelClient:
    """Connect to the session's kernel; lookup, start and save share one transaction."""
    project = Path(path).expanduser().resolve()
    kernel_name = get_session_kernel_name(project, session_id)

    with storage.transaction() as conn:
        stored = storage.load_entry(kernel_name, conn=conn)
        kc = _reconnect(kernel_name, stored, timeout, conn) if stored else None

        if kc:
            return kc

        kc = _connect_new_kernel(project, timeout)
        storage.save_entry(kernel_name, str(kc.connection_file), path, conn=conn)

    return kc


def close(project: Path, session_id: str) -> None:
    kernel_name = get_session_kernel_name(project, session_id)

    with storage.transaction() as conn:
        stored = storage.load_entry(kernel_name, conn=conn)

        if not stored:
            print("not running")
            return

        shutdown_adopted(stored["connection_file"])
        storage.delete_entry(kernel_name, conn=conn)
