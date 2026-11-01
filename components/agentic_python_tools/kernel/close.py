import time
from pathlib import Path

from jupyter_client import BlockingKernelClient


def shutdown_adopted(connection_file: str) -> None:
    """Shut down a kernel we didn't spawn and clean up its files."""
    kc = BlockingKernelClient()

    try:
        kc.load_connection_file(connection_file)
    except FileNotFoundError:
        return

    try:
        kc.start_channels()
        kc.shutdown()
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            if not kc.is_alive():
                break

            time.sleep(0.2)
    finally:
        kc.stop_channels()

    Path(connection_file).unlink(missing_ok=True)

    for f in Path(connection_file).parent.glob(Path(connection_file).stem + "-ipc-*"):
        f.unlink(missing_ok=True)
