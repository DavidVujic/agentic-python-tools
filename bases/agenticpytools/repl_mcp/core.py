from pathlib import Path

from agenticpytools.kernel import capture, client
from fastmcp import FastMCP

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

    kc = client.create(project, TIMEOUT)

    msg_id = kc.execute(data)
    stdout, stderr, result, error = capture(kc, msg_id, TIMEOUT)

    return {"stdout": stdout, "stderr": stderr, "result": result, "error": error}


@mcp.tool
def close(project_full_path: str) -> None:
    """Close the kernel."""
    project = Path(project_full_path).expanduser().resolve()

    client.close(project, TIMEOUT)


if __name__ == "__main__":
    mcp.run()
