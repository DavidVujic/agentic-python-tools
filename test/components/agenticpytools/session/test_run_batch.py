"""Unit tests for a session running its kinds on a watcher batch."""

from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from agenticpytools.runner import run_commands
from agenticpytools.session import KINDS, latest, start
from agenticpytools.session.core import DETECTORS, _mark_pending, _run_batch

pytestmark = pytest.mark.session

CANNED_LINT_COMMAND = {"argv": ["ruff", "check"]}


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _uv_project_with_ruff_ty_pytest(project: Path) -> None:
    """A uv project whose dev group depends on ruff, ty, and pytest."""
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["ruff", "ty", "pytest"]\n'
    )


def _results(commands: list[dict]) -> list[dict]:
    return [
        {"argv": c["argv"], "returncode": 0, "stdout": "", "stderr": ""}
        for c in commands
    ]


def _fake_run(calls: list):
    def run(commands, files=None, timeout=60.0):
        calls.append((commands, files))

        return _results(commands)

    return run


def _wait_until(condition, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout

    while monotonic() < deadline:
        if condition():
            return True

        sleep(0.05)

    return False


def _initial_done(session: dict) -> bool:
    """Whether no run of any kind is scheduled or in progress."""
    return not any(latest(session, kind)["running"] for kind in KINDS)


def _start_and_wait(project: Path, session_id: str, run) -> dict:
    """Start a session and wait for its background initial runs to finish."""
    session = start(project, session_id, run=run)

    assert _wait_until(lambda: _initial_done(session)), "initial runs did not finish"

    return session


def _batch_session(project: Path) -> dict:
    """A minimal session with one canned command per kind."""
    return {
        "project": str(project),
        "commands": {kind: [CANNED_LINT_COMMAND] for kind in KINDS},
        "latest": {},
        "pending": dict.fromkeys(KINDS, 0),
        "stop": Event(),
    }


def test_run_batch_runs_all_kinds(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    calls: list = []
    session = _start_and_wait(tmp_path, "s1", _fake_run(calls))

    _run_batch(session, _fake_run(calls), ["x.py"], _mark_pending(session))

    for kind in KINDS:
        assert latest(session, kind)["origin"] == "watcher"
        assert latest(session, kind)["changed_files"] == ["x.py"]
        assert latest(session, kind)["running"] is False


def test_run_batch_passes_only_existing_files(tmp_path):
    (tmp_path / "kept.py").write_text("x = 1\n")
    session = _batch_session(tmp_path)
    calls: list = []

    _run_batch(
        session, _fake_run(calls), ["gone.py", "kept.py"], _mark_pending(session)
    )

    files_seen = [files for _, files in calls]

    assert files_seen.count(["kept.py"]) == 2
    assert files_seen.count(None) == 1
    for kind in KINDS:
        assert session["latest"][kind]["changed_files"] == ["gone.py", "kept.py"]


def test_run_batch_runs_whole_project_when_all_deleted(tmp_path):
    session = _batch_session(tmp_path)
    calls: list = []

    _run_batch(session, _fake_run(calls), ["gone.py"], _mark_pending(session))

    assert [files for _, files in calls] == [None] * len(KINDS)
    for kind in KINDS:
        assert session["latest"][kind]["origin"] == "watcher"
        assert session["latest"][kind]["changed_files"] == ["gone.py"]


def test_run_batch_runs_affected_tests_on_production_file_change(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "module.py").write_text("x = 1\n")
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_module.py").write_text("from pkg import module\n")
    argvs: list = []

    def fake_subprocess_run(argv, **kwargs):
        argvs.append(argv)

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "agenticpytools.runner.core.subprocess.run", fake_subprocess_run
    )
    session = _batch_session(tmp_path)
    session["commands"] = {kind: DETECTORS[kind](tmp_path) for kind in KINDS}

    _run_batch(session, run_commands, ["pkg/module.py"], _mark_pending(session))

    pytest_argvs = [argv for argv in argvs if argv[:3] == ["uv", "run", "pytest"]]
    assert pytest_argvs == [["uv", "run", "pytest", "test/test_module.py"]]
    assert ["uv", "run", "ruff", "check", "pkg/module.py"] in argvs
    assert ["uv", "run", "ty", "check", "pkg/module.py"] in argvs
    assert session["latest"]["test"]["changed_files"] == ["pkg/module.py"]


def test_run_batch_publishes_note_when_no_test_is_affected(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "module.py").write_text("x = 1\n")
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_unrelated.py").write_text(
        "def test_unrelated():\n    assert True\n"
    )
    session = _batch_session(tmp_path)
    session["commands"] = {
        kind: [{"argv": [tool]}] for kind, tool in zip(KINDS, ("ruff", "ty", "pytest"))
    }
    calls: list = []

    _run_batch(session, _fake_run(calls), ["pkg/module.py"], _mark_pending(session))

    assert sorted((commands[0]["argv"][0], files) for commands, files in calls) == [
        ("ruff", ["pkg/module.py"]),
        ("ty", ["pkg/module.py"]),
    ]
    entry = latest(session, "test")

    assert entry["ok"] is True
    assert entry["results"] is None
    assert entry["note"] == "no affected tests"
    assert entry["origin"] == "watcher"
    assert entry["changed_files"] == ["pkg/module.py"]
    assert entry["running"] is False


def test_run_batch_cancels_pending_kinds_once_stopped(tmp_path):
    session = _batch_session(tmp_path)
    session["pending"] = dict.fromkeys(KINDS, 1)
    session["stop"].set()
    calls: list = []

    _run_batch(session, _fake_run(calls), None, KINDS)

    assert calls == []
    assert _mark_pending(session) == ()
    for kind in KINDS:
        entry = latest(session, kind)

        assert entry["origin"] == "initial"
        assert entry["results"] is None
        assert entry["ok"] is None
        assert entry["note"] == f"{kind} run cancelled: session stopped"
        assert entry["running"] is False
