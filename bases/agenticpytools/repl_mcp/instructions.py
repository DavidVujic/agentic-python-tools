summary = (
    "Persistent Python REPL: one Jupyter kernel per project and session, keyed by project_full_path and session_id. "
    "session_id is any non-empty string that stays the same for your whole session and differs from other concurrent sessions. "
    "Use your chat ID if one is available and unique to your agent session; otherwise generate a UUIDv4 once with a real generator. "
    "Never fabricate a predictable ID from the project or task. "
    "Pass the same session_id, with the same absolute project_full_path, to every run and close. "
    "A different path or session_id starts a different kernel. "
    "Keep the kernel alive for the entire session: state (imports, definitions, values) persists between run calls, "
    "so import once and reuse; send small focused snippets rather than long scripts. "
    "Call close(project_full_path, session_id) only when finished with the REPL, such as at the end of session or task, "
    "or to deliberately reset state — e.g. if results contradict the source code, because an in-memory redefinition may be shadowing it. "
    "After close, the next run starts a fresh kernel. "
    "In-memory redefinitions affect later run calls but never modify source files; edits to source files are picked up automatically on the next run. "
)
