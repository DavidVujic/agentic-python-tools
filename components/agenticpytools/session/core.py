"""Session state: background watching of a project's check commands."""

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from agenticpytools.linter import detect_lint_commands
from agenticpytools.runner import run_commands
from agenticpytools.tester import detect_test_commands
from agenticpytools.typechecker import detect_typecheck_commands
from agenticpytools.watcher import changed_python_files

KINDS = ("lint", "typecheck", "test")
DETECTORS = {
    "lint": detect_lint_commands,
    "typecheck": detect_typecheck_commands,
    "test": detect_test_commands,
}
SESSION_ID_ERROR_MESSAGE = "session_id must be a non-empty string"

_SESSIONS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _session_key(project: Path, session_id: str) -> str:
    """Registry key of a session watching a project."""
    if not session_id.strip():
        raise ValueError(SESSION_ID_ERROR_MESSAGE)

    return json.dumps([session_id, str(Path(project).expanduser().resolve())])


def start(
    project: Path, session_id: str, run: Callable[..., list[dict]] | None = None
) -> dict:
    """Start watching a project without waiting for checks; idempotent per session."""
    if run is None:
        run = run_commands

    path = Path(project).expanduser().resolve()
    key = _session_key(project, session_id)

    with _LOCK:
        if key in _SESSIONS:
            return _SESSIONS[key]

        detected = {kind: DETECTORS[kind](path) for kind in KINDS}
        kinds = tuple(kind for kind in KINDS if detected[kind])
        session = {
            "project": str(path),
            "session_id": session_id,
            "commands": detected,
            "latest": {},
            "pending": {kind: int(kind in kinds) for kind in KINDS},
            "thread": None,
            "stop": threading.Event(),
            "initial_done": threading.Event(),
        }
        thread = threading.Thread(
            target=_run_in_background, args=(session, run, kinds), daemon=True
        )
        session["thread"] = thread
        thread.start()
        _SESSIONS[key] = session

    return session


def _run_in_background(
    session: dict, run: Callable[..., list[dict]], kinds: tuple[str, ...]
) -> None:
    """Warm the caches with the initial runs, then rerun on file changes."""
    _run_initial(session, run, kinds)
    _watch(session, run)


def _run_initial(
    session: dict, run: Callable[..., list[dict]], kinds: tuple[str, ...]
) -> None:
    """Run the kinds marked pending at start once, then mark the initial runs done."""
    try:
        _run_batch(session, run, None, kinds)
    finally:
        session["initial_done"].set()


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


def _outcome_entry(job: dict, ok: bool | None, note: str) -> dict:
    """Cache entry for a run without results, such as a failed or cancelled one."""
    entry = _latest_entry(job["kind"], None, job["changed_files"], job["origin"])

    return {**entry, "ok": ok, "note": note}


def _run_job(
    run: Callable[..., list[dict]], cmds: list[dict], files: list[str] | None, job: dict
) -> dict:
    """Run a kind's commands into a cache entry; a raising run becomes a failed entry."""
    try:
        results = run(cmds, files=files)
    except Exception as exc:  # noqa: BLE001
        # Any failure must still publish an outcome, so its pending state is released.
        return _outcome_entry(job, False, f"{job['kind']} run failed: {exc}")

    return _latest_entry(job["kind"], results, job["changed_files"], job["origin"])


def _is_newer(entry: dict, existing: dict) -> bool:
    """True when the given entry ran at or after the cached one."""
    return (existing.get("ran_at") or "") <= (entry.get("ran_at") or "")


def _is_running(session: dict, kind: str) -> bool:
    """True while a run of the kind is scheduled or in progress; call under _LOCK."""
    return session["pending"][kind] > 0


def _mark_pending(session: dict) -> tuple[str, ...]:
    """Mark every kind with commands as pending, unless the session is stopping."""
    with _LOCK:
        if session["stop"].is_set():
            return ()

        kinds = tuple(kind for kind in KINDS if session["commands"][kind])

        for kind in kinds:
            session["pending"][kind] += 1

    return kinds


def _publish(session: dict, entry: dict) -> None:
    """Cache the newer entry per kind and release one pending run of that kind."""
    kind = entry["kind"]

    with _LOCK:
        existing = session["latest"].get(kind)

        if existing is None or _is_newer(entry, existing):
            session["latest"][kind] = entry

        session["pending"][kind] = max(session["pending"][kind] - 1, 0)


def _watch(session: dict, run: Callable[..., list[dict]]) -> None:
    """Rerun the check commands whenever watched Python files change."""
    for batch in changed_python_files(
        Path(session["project"]), stop_event=session["stop"]
    ):
        if session["stop"].is_set():
            break

        _run_batch(session, run, batch, _mark_pending(session))


def _existing_files(project: str, batch: list[str]) -> list[str] | None:
    """The batch's files that still exist; None runs on the whole project."""
    existing = [f for f in batch if (Path(project) / f).is_file()]

    return existing or None


def _run_batch(
    session: dict,
    run: Callable[..., list[dict]],
    batch: list[str] | None,
    kinds: tuple[str, ...],
) -> None:
    """Run the pending kinds once, publishing each outcome as it finishes.

    A watcher batch runs on its changed files; a None batch is the initial run.
    """
    files = _existing_files(session["project"], batch) if batch else None
    origin = "watcher" if batch else "initial"

    def run_kind(kind: str) -> None:
        job = {"kind": kind, "changed_files": batch or [], "origin": origin}

        if session["stop"].is_set():
            entry = _outcome_entry(job, None, f"{kind} run cancelled: session stopped")
        else:
            entry = _run_job(run, session["commands"][kind], files, job)

        _publish(session, entry)

    with ThreadPoolExecutor(max_workers=len(KINDS)) as executor:
        list(executor.map(run_kind, kinds))


def latest(session: dict, kind: str = "lint") -> dict:
    """The latest cached entry for a kind, with that kind's running flag."""
    with _LOCK:
        entry = session["latest"].get(kind) or _default_entry(kind)

        return {**entry, "running": _is_running(session, kind)}


def _serve_or_claim(session: dict, kind: str, claim: bool) -> dict | None:
    """The response to serve now, or None when nothing is cached or in flight.

    A completed run is served as is, including a failed or cancelled one, so it is
    never retried on demand. With claim, None also marks a new on-demand run pending.
    """
    with _LOCK:
        entry = session["latest"].get(kind)
        running = _is_running(session, kind)

        if entry is not None:
            return {**entry, "running": running}

        if running:
            return {**_default_entry(kind), "running": True}

        if claim:
            session["pending"][kind] += 1

    return None


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

    served = _serve_or_claim(session, kind, claim=False) if session else None

    if served is not None:
        return served

    session_cmds = session["commands"].get(kind) if session else []
    cmds = session_cmds or DETECTORS.get(kind, lambda p: [])(path)

    if not cmds:
        return {
            **_default_entry(kind),
            "origin": "none",
            "running": False,
            "note": f"no {kind} commands detected for project",
        }

    job = {"kind": kind, "changed_files": [], "origin": "on-demand"}

    if session is None:
        return {**_run_job(run, cmds, None, job), "running": False}

    served = _serve_or_claim(session, kind, claim=True)

    if served is not None:
        return served

    _publish(session, _run_job(run, cmds, None, job))

    return latest(session, kind)


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
    """Stop a session's background runs and watcher and remove it; False when no session exists."""
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
