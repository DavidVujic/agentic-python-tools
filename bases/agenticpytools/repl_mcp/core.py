from pathlib import Path
from typing import Any

from agenticpytools.kernel import capture, client
from agenticpytools.repl_mcp.instructions import summary
from fastmcp import FastMCP

mcp = FastMCP(name="agent-python-repl-mcp", instructions=summary)

TIMEOUT = 30


def return_data(
    stdout: list | None = None,
    stderr: list | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> dict[str, Any | None]:
    return {"stdout": stdout, "stderr": stderr, "result": result, "error": error}


@mcp.tool
def run(data: str, project_full_path: str, session_id: str) -> dict[str, Any | None]:
    """Execute code in the session's kernel and return the output.

    session_id: a non-empty string, stable for the whole session and unique among
    concurrent sessions; prefer the host's chat or session ID, else a UUID generated once.

    Returns a dictionary
    stdout: from standard output
    stderr: from standard error
    result: from code evaluation
    error: any caught errors during evaluation
    """
    kc = client.create(project_full_path, session_id, TIMEOUT)

    try:
        msg_id = kc.execute(data)

        try:
            stdout, stderr, result, error = capture(kc, msg_id, TIMEOUT)
        except TimeoutError:
            return return_data(error="Timeout: try again.")

        return return_data(stdout, stderr, result, error)
    finally:
        kc.stop_channels()


@mcp.tool
def close(project_full_path: str, session_id: str) -> None:
    """Close the session's kernel."""
    project = Path(project_full_path).expanduser().resolve()

    client.close(project, session_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
