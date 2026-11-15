"""Session state: background watching of a project's lint commands."""

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from agenticpytools.linter import detect_lint_commands
from agenticpytools.runner import run_commands
from agenticpytools.watcher import changed_python_files

_SESSIONS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _session_key(project: Path, session_id: str) -> str:
    """Registry key of a session watching a project."""
    if not session_id.strip():
        raise ValueError("session_id must be a non-empty string")

    return json.dumps([session_id, str(Path(project).expanduser().resolve())])


def start(
    project: Path, session_id: str, run: Callable[..., list[dict]] | None = None
) -> dict:
    """Start watching a project's lint commands; idempotent per session."""
    if run is None:
        run = run_commands

    path = Path(project).expanduser().resolve()
    key = _session_key(project, session_id)

    with _LOCK:
        if key in _SESSIONS:
            return _SESSIONS[key]

        session = {
            "project": str(path),
            "session_id": session_id,
            "commands": {"lint": detect_lint_commands(path)},
            "latest": {},
            "running": False,
            "thread": None,
            "stop": threading.Event(),
        }
        _SESSIONS[key] = session

        try:
            if session["commands"]["lint"]:
                results = run(session["commands"]["lint"], files=None)
                session["latest"]["lint"] = _latest_entry(
                    "lint", results, files=[], origin="initial"
                )

            thread = threading.Thread(target=_watch, args=(session, run), daemon=True)
            session["thread"] = thread
            thread.start()
        except Exception:
            _SESSIONS.pop(key, None)
            raise

    return session


def _default_entry(kind: str) -> dict:
    """Placeholder entry for a kind with no cached run yet."""
    return {
        "kind": kind,
        "results": None,
        "ran_at": None,
        "changed_files": [],
        "ok": None,
        "origin": None,
    }


def _latest_entry(
    kind: str, results: list[dict] | None, files: list[str], origin: str
) -> dict:
    """One cache entry for a finished run of a command kind."""
    ok = all(r["returncode"] == 0 for r in results) if results is not None else None

    return {
        "kind": kind,
        "results": results,
        "ran_at": datetime.now(UTC).isoformat(),
        "changed_files": list(files),
        "ok": ok,
        "origin": origin,
    }


def _is_newer(entry: dict, existing: dict) -> bool:
    """True when the given entry ran at or after the cached one."""
    return (existing.get("ran_at") or "") <= (entry.get("ran_at") or "")


def _store_latest(session: dict, entry: dict) -> None:
    """Cache the newer entry per kind; a stale run never overwrites a newer one."""
    with _LOCK:
        existing = session["latest"].get(entry["kind"])

        if existing is None or _is_newer(entry, existing):
            session["latest"][entry["kind"]] = entry


def _watch(session: dict, run: Callable[..., list[dict]]) -> None:
    """Rerun the lint commands whenever watched Python files change."""
    for batch in changed_python_files(
        Path(session["project"]), stop_event=session["stop"]
    ):
        if session["stop"].is_set():
            break

        try:
            with _LOCK:
                session["running"] = True
            results = run(session["commands"]["lint"], files=batch)
            _store_latest(
                session, _latest_entry("lint", results, batch, origin="watcher")
            )
        finally:
            with _LOCK:
                session["running"] = False


def latest(session: dict, kind: str = "lint") -> dict:
    """The latest cached entry for a kind, with the running flag."""
    with _LOCK:
        entry = session["latest"].get(kind) or _default_entry(kind)

        return {**entry, "running": session["running"]}


def _in_flight_state(entry: dict | None) -> dict:
    """The state to serve while a watcher run is in flight."""
    return {**(entry or _default_entry("lint")), "running": True}


def lint(
    project: Path, session_id: str, run: Callable[..., list[dict]] | None = None
) -> dict:
    """Latest cached lint entry if ready; otherwise detect and run lint now."""
    if run is None:
        run = run_commands

    path = Path(project).expanduser().resolve()
    key = _session_key(project, session_id)

    with _LOCK:
        session = _SESSIONS.get(key)
        entry = session["latest"].get("lint") if session else None
        running = session["running"] if session else False

    if entry is not None:
        return {**entry, "running": running}

    if session is not None and running:
        return _in_flight_state(entry)

    session_commands = session["commands"]["lint"] if session else []
    lint_commands = session_commands or detect_lint_commands(path)

    if not lint_commands:
        return {
            "kind": "lint",
            "results": None,
            "ran_at": None,
            "changed_files": [],
            "ok": None,
            "origin": "none",
            "running": running,
            "note": "no lint commands detected for project",
        }

    results = run(lint_commands, files=None)
    entry = _latest_entry("lint", results, files=[], origin="on-demand")

    if session is not None:
        _store_latest(session, entry)

    return {**entry, "running": running}


def commands(session: dict) -> dict:
    """The commands detected for the session's project."""
    return session["commands"]


def get(project: Path, session_id: str) -> dict | None:
    """The session watching a project for a session_id, if any."""
    with _LOCK:
        return _SESSIONS.get(_session_key(project, session_id))


def stop(project: Path, session_id: str) -> bool:
    """Stop a session's watcher and remove it; False when no session exists."""
    key = _session_key(project, session_id)

    with _LOCK:
        session = _SESSIONS.pop(key, None)

        if session is None:
            return False

        session["stop"].set()
        thread = session["thread"]

    if thread is not None:
        thread.join(timeout=5)

    return True
