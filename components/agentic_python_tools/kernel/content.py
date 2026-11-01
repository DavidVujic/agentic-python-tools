from queue import Empty
from typing import Any

from jupyter_client import BlockingKernelClient


def capture(
    kc: BlockingKernelClient,
    msg_id: Any,
    timeout: int = 30,
) -> tuple[list, list, dict[str, Any] | None, str | None]:
    """Capture the stdout, stderr, result and error."""
    stdout, stderr, result, error = [], [], None, None

    while True:
        try:
            msg = kc.get_iopub_msg(timeout=timeout)
        except Empty:
            raise TimeoutError("kernel didn't finish")

        if msg["parent_header"].get("msg_id") != msg_id:
            continue

        msg_type = msg["header"]["msg_type"]
        content = msg["content"]

        if msg_type == "stream":
            (stdout if content["name"] == "stdout" else stderr).append(content["text"])
        elif msg_type in ("display_data", "execute_result"):
            result = content["data"]
        elif msg_type == "error":
            error = "\n".join(content["traceback"])
        elif msg_type == "status" and content["execution_state"] == "idle":
            break

    return stdout, stderr, result, error
