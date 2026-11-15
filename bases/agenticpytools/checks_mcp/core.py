"""MCP server: watch a project and serve cached lint results."""

from pathlib import Path

from agenticpytools import session as sessions
from agenticpytools.checks_mcp.instructions import summary
from agenticpytools.linter import detect_lint_commands
from fastmcp import FastMCP

mcp = FastMCP(name="checks-mcp", instructions=summary)


@mcp.tool
def start_watching(project_full_path: str, session_id: str) -> dict:
    """Start watching a project; returns its commands and initial lint results."""
    if not session_id.strip():
        return {"error": "session_id must be a non-empty string"}

    try:
        session = sessions.start(Path(project_full_path), session_id)

        return {
            "project": session["project"],
            "session_id": session_id,
            "watching": True,
            "commands": sessions.commands(session),
            "initial": sessions.latest(session, "lint"),
        }
    except (OSError, ValueError) as exc:
        return {"error": f"failed to start watching: {exc}"}


@mcp.tool
def detected_commands(project_full_path: str, session_id: str) -> dict:
    """The lint commands for a watched session, detected on demand otherwise."""
    if not session_id.strip():
        return {"error": "session_id must be a non-empty string"}

    try:
        session = sessions.get(Path(project_full_path), session_id)

        if session is not None:
            return sessions.commands(session)

        return {"lint": detect_lint_commands(Path(project_full_path))}
    except (OSError, ValueError) as exc:
        return {"error": f"failed to detect commands: {exc}"}


@mcp.tool
def lint(project_full_path: str, session_id: str) -> dict:
    """Latest cached lint results for the session; runs lint on demand if not ready."""
    if not session_id.strip():
        return {"error": "session_id must be a non-empty string"}

    try:
        return sessions.lint(Path(project_full_path), session_id)
    except (OSError, ValueError) as exc:
        return {"error": f"failed to run lint: {exc}"}


@mcp.tool
def stop_watching(project_full_path: str, session_id: str) -> dict:
    """Stop watching a project session; the watcher thread exits."""
    if not session_id.strip():
        return {"error": "session_id must be a non-empty string"}

    try:
        stopped = sessions.stop(Path(project_full_path), session_id)
    except (OSError, ValueError) as exc:
        return {"error": f"failed to stop watching: {exc}"}

    if not stopped:
        return {"error": "no session for this project_full_path/session_id"}

    return {
        "project": str(Path(project_full_path).expanduser().resolve()),
        "session_id": session_id,
        "stopped": True,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
