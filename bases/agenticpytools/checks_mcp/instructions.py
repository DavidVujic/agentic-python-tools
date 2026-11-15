"""Instructions for the checks MCP server."""

summary = (
    "An MCP server that watches a target project during an agent session. "
    "Every tool takes project_full_path and session_id. "
    "Call start_watching(project_full_path, session_id) once per session. "
    "Then lint(project_full_path, session_id), typecheck(project_full_path, "
    "session_id), and test(project_full_path, session_id) return the cached "
    "lint, typecheck, and test results when a ready result exists, otherwise "
    "run the commands on demand and return the result; no session required. "
    'Results include an "origin" field: "watcher" | "initial" | "on-demand" '
    '(| "none" when no commands of that kind were detected), indicating '
    "whether the watcher already ran them or they ran on demand. "
    "detected_commands(project_full_path, session_id) returns the watched "
    "session's lint, typecheck, and test commands, or detects them on "
    "demand without a watcher. "
    "stop_watching(project_full_path, session_id) stops the watcher and "
    "removes the session."
)
