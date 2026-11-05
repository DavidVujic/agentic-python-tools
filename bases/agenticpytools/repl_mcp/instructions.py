summary = (
    "Persistent Python REPL: one Jupyter kernel per project, keyed by project_full_path. "
    "Always pass the same absolute project_full_path to run and close. "
    "A different path starts a different kernel. "
    "Keep the kernel alive for the entire session: state (imports, definitions, values) persists between run calls, "
    "so import once and reuse; send small focused snippets rather than long scripts. "
    "Call close(project_full_path) only when finished with the REPL, such as at the end of session or task, "
    "or to deliberately reset state — e.g. if results contradict the source code, because an in-memory redefinition may be shadowing it. "
    "After close, the next run starts a fresh kernel. "
    "In-memory redefinitions affect later run calls but never modify source files; edits to source files are picked up automatically on the next run. "
)
