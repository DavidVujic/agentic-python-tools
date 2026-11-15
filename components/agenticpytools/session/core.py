"""Session state: background watching of a project's check commands."""

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from agenticpytools.linter import detect_lint_commands
from agenticpytools.runner import run_commands
from agenticpytools.typechecker import detect_typecheck_commands
from agenticpytools.watcher import changed_python_files

KINDS = ("lint", "typecheck")
DETECTORS = {"lint": detect_lint_commands, "typecheck": detect_typecheck_commands}

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
    """Start watching a project's check commands; idempotent per session."""
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
            "commands": {kind: DETECTORS[kind](path) for kind in KINDS},
            "latest": {},
            "running": True,
            "thread": None,
            "stop": threading.Event(),
        }
        _SESSIONS[key] = session

    try:
        _run_initial(session, run)
    except Exception:
        with _LOCK:
            _SESSIONS.pop(key, None)
            session["running"] = False

        raise

    with _LOCK:
        session["running"] = False
        thread = threading.Thread(target=_watch, args=(session, run), daemon=True)
        session["thread"] = thread

        try:
            thread.start()
        except Exception:
            _SESSIONS.pop(key, None)
            raise

    return session


def _run_initial(session: dict, run: Callable[..., list[dict]]) -> None:
    """Run every kind's commands once at session start."""
    for kind in KINDS:
        cmds = session["commands"][kind]

        if cmds:
            results = run(cmds, files=None)
            _store_latest(session, _latest_entry(kind, results, [], origin="initial"))


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
    """Rerun the check commands whenever watched Python files change."""
    for batch in changed_python_files(
        Path(session["project"]), stop_event=session["stop"]
    ):
        if session["stop"].is_set():
            break

        try:
            with _LOCK:
                session["running"] = True

            _run_batch(session, run, batch)
        finally:
            with _LOCK:
                session["running"] = False


def _run_batch(session: dict, run: Callable[..., list[dict]], batch: list[str]) -> None:
    """Run every kind's commands once for a batch of changed files."""

    def run_kind(kind: str) -> None:
        cmds = session["commands"][kind]

        if cmds:
            results = run(cmds, files=batch)
            _store_latest(
                session,
                _latest_entry(kind, results, batch, origin="watcher"),
            )

    with ThreadPoolExecutor(max_workers=len(KINDS)) as executor:
        list(executor.map(run_kind, KINDS))


def latest(session: dict, kind: str = "lint") -> dict:
    """The latest cached entry for a kind, with the running flag."""
    with _LOCK:
        entry = session["latest"].get(kind) or _default_entry(kind)

        return {**entry, "running": session["running"]}


def _in_flight_state(entry: dict | None, kind: str) -> dict:
    """The state to serve while a watcher run is in flight."""
    return {**(entry or _default_entry(kind)), "running": True}


def run_check(
    project: Path,
    session_id: str,
    kind: str,
    run: Callable[..., list[dict]] | None = None,
) -> dict:
    """Latest cached entry for a kind if ready; otherwise detect and run now."""
    if run is None:
        run = run_commands

    path = Path(project).expanduser().resolve()
    key = _session_key(project, session_id)

    with _LOCK:
        session = _SESSIONS.get(key)
        entry = session["latest"].get(kind) if session else None
        running = session["running"] if session else False

    if entry is not None:
        return {**entry, "running": running}

    if session is not None and running:
        return _in_flight_state(entry, kind)

    session_cmds = session["commands"].get(kind) if session else []
    cmds = session_cmds or DETECTORS.get(kind, lambda p: [])(path)

    if not cmds:
        return {
            **_default_entry(kind),
            "origin": "none",
            "running": running,
            "note": f"no {kind} commands detected for project",
        }

    results = run(cmds, files=None)
    entry = _latest_entry(kind, results, files=[], origin="on-demand")

    if session is not None:
        _store_latest(session, entry)

    return {**entry, "running": running}


def lint(
    project: Path, session_id: str, run: Callable[..., list[dict]] | None = None
) -> dict:
    """Latest cached lint entry if ready; otherwise detect and run lint now."""
    return run_check(project, session_id, "lint", run)


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
