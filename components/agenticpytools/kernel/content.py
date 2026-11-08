from queue import Empty
from typing import Any

from jupyter_client import BlockingKernelClient


def _handle_message(msg: dict, acc: dict[str, Any]) -> bool:
    """Apply one iopub message to ACC. Return True when the kernel went idle."""
    header = msg["header"]
    content = msg["content"]
    msg_type = header["msg_type"]

    if msg_type == "stream":
        key = "stdout" if content["name"] == "stdout" else "stderr"
        acc[key].append(content["text"])
    elif msg_type in ("display_data", "execute_result"):
        acc["result"] = content["data"]
    elif msg_type == "error":
        acc["error"] = "\n".join(content["traceback"])
    elif msg_type == "status":
        return content["execution_state"] == "idle"

    return False


def capture(
    kc: BlockingKernelClient,
    msg_id: Any,
    timeout: int,
) -> tuple[list, list, dict[str, Any] | None, str | None]:
    """Capture the stdout, stderr, result and error."""
    acc: dict[str, Any] = {"stdout": [], "stderr": [], "result": None, "error": None}

    while True:
        try:
            msg = kc.get_iopub_msg(timeout=timeout)
        except Empty:
            raise TimeoutError("kernel didn't finish")

        if msg["parent_header"].get("msg_id") != msg_id:
            continue

        if _handle_message(msg, acc):
            break

    return acc["stdout"], acc["stderr"], acc["result"], acc["error"]
