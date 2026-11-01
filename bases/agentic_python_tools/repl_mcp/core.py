import json
from pathlib import Path

from agentic_python_tools import storage
from agentic_python_tools.kernel import (
    capture,
    create_and_start_kernel,
    get_kernel_name,
    is_running_stored,
    shutdown_adopted,
)
from fastmcp import FastMCP
from jupyter_client import BlockingKernelClient

mcp = FastMCP("My MCP Server")

TIMEOUT = 30


@mcp.tool
def run(data: str, project_full_path: str) -> dict:
    """Execute code in the kernel and return the output.

    Output format
    stdout: from standard output
    stderr: from standard error
    result: from code evaluation
    error: any caught errors during evaluation
    """
    project = Path(project_full_path).expanduser().resolve()
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    freshly_started = not (stored and is_running_stored(stored))

    if freshly_started:
        # Shut down the existing kernel if it exists and is not reusable
        if stored and not is_running_stored(stored):
            shutdown_adopted(stored["connection_file"])

        km = create_and_start_kernel(project)
        kc = km.client()
        storage.save_entry(kernel_name, str(km.connection_file), project_full_path)
    else:
        try:
            kc = BlockingKernelClient()
            kc.load_connection_file(stored["connection_file"])
            kc.start_channels()
            kc.wait_for_ready(timeout=TIMEOUT)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, RuntimeError) as e:
            kc.stop_channels()
            raise RuntimeError(f"Failed to connect to external kernel: {e}")

    # 3. Execute (client stays connected — do NOT call stop_channels here)
    msg_id = kc.execute(data)
    stdout, stderr, result, error = capture(kc, msg_id)

    return {"stdout": stdout, "stderr": stderr, "result": result, "error": error}


@mcp.tool
def close(project_full_path: str) -> None:
    """Close the kernel."""
    project = Path(project_full_path).expanduser().resolve()
    kernel_name = get_kernel_name(project.name)

    stored = storage.load_entry(kernel_name)

    if not stored or not is_running_stored(stored):
        print("not running")
        return

    # retire the cached client FIRST (it's about to be useless)
    kc = stored.get("client")
    if kc is not None:
        kc.stop_channels()

    # then shut the kernel down via the standalone path (as you already have)
    shutdown_adopted(stored["connection_file"])


if __name__ == "__main__":
    mcp.run()
