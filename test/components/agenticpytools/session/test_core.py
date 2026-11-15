"""Unit tests for session state: background watching of check commands."""

from pathlib import Path
from time import monotonic, sleep

import pytest
from agenticpytools.session import (
    commands,
    get,
    latest,
    lint,
    run_check,
    start,
    stop,
)
from agenticpytools.session.core import (
    DETECTORS,
    _run_batch,
    _session_key,
    _store_latest,
)

pytestmark = pytest.mark.session

CANNED_LINT_COMMAND = {"argv": ["ruff", "check"]}
CANNED_TYPECHECK_COMMAND = {"argv": ["ty", "check"]}
CANNED_TEST_COMMAND = {"argv": ["pytest"]}


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _uv_project_with_ruff(project: Path) -> None:
    """A uv project whose dev group depends on ruff."""
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text('[dependency-groups]\ndev = ["ruff"]\n')


def _uv_project_with_ruff_ty_pytest(project: Path) -> None:
    """A uv project whose dev group depends on ruff, ty, and pytest."""
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["ruff", "ty", "pytest"]\n'
    )


def _fake_run(calls: list):
    def run(commands, files=None, timeout=60.0):
        calls.append((commands, files))

        return [
            {"argv": c["argv"], "returncode": 0, "stdout": "", "stderr": ""}
            for c in commands
        ]

    return run


def _wait_until(condition, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout

    while monotonic() < deadline:
        if condition():
            return True

        sleep(0.05)

    return False


def test_start_detects_and_runs_once(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    assert [c["argv"] for c in commands(session)["lint"]] == [
        ["uv", "run", "ruff", "check"],
        ["uv", "run", "ruff", "format", "--check"],
    ]
    assert len(calls) == 1
    assert calls[0][1] is None
    assert latest(session)["ok"] is True
    assert latest(session)["running"] is False
    assert latest(session)["origin"] == "initial"
    assert get(tmp_path, "s1") is session


def test_start_detects_and_runs_all_kinds(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    assert [c["argv"] for c in commands(session)["lint"]] == [
        ["uv", "run", "ruff", "check"],
        ["uv", "run", "ruff", "format", "--check"],
    ]
    assert [c["argv"] for c in commands(session)["typecheck"]] == [
        ["uv", "run", "ty", "check"]
    ]
    assert [c["argv"] for c in commands(session)["test"]] == [["uv", "run", "pytest"]]
    assert len(calls) == 3
    assert latest(session, "lint")["origin"] == "initial"
    assert latest(session, "typecheck")["origin"] == "initial"
    assert latest(session, "test")["origin"] == "initial"


def test_start_is_idempotent(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    second_calls: list = []

    assert start(tmp_path, "s1", run=_fake_run(second_calls)) is session
    assert second_calls == []
    assert len(calls) == 1


def test_sessions_are_separate_per_session_id(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    other_calls: list = []
    other = start(tmp_path, "s2", run=_fake_run(other_calls))

    assert other is not session
    assert get(tmp_path, "s1") is session
    assert get(tmp_path, "s2") is other
    assert len(calls) == 1
    assert len(other_calls) == 1


def test_empty_session_id_raises(tmp_path):
    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        start(tmp_path, "")


def test_start_initial_run_failure_removes_session(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)

    def failing_run(commands, files=None):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        start(tmp_path, "s1", run=failing_run)

    assert get(tmp_path, "s1") is None


def test_session_key_is_unambiguous():
    assert _session_key(Path("/x"), "a:b") != _session_key(Path("b:/x"), "a")


def test_watcher_thread_reruns_on_change(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    first_ran_at = latest(session)["ran_at"]

    sleep(0.2)
    (tmp_path / "new.py").write_text("x = 1\n")

    assert _wait_until(lambda: len(calls) >= 2), "watcher did not rerun"
    assert calls[-1][1] == ["new.py"]
    assert _wait_until(lambda: latest(session)["changed_files"] == ["new.py"])
    assert latest(session)["ran_at"] != first_ran_at
    assert latest(session)["origin"] == "watcher"


def test_watcher_reruns_all_kinds_on_change(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    sleep(0.2)
    (tmp_path / "new.py").write_text("x = 1\n")

    assert _wait_until(
        lambda: all(
            latest(session, kind)["origin"] == "watcher"
            for kind in ("lint", "typecheck", "test")
        )
    ), "watcher did not rerun all kinds"
    assert latest(session, "lint")["changed_files"] == ["new.py"]
    assert latest(session, "typecheck")["changed_files"] == ["new.py"]
    assert latest(session, "test")["changed_files"] == ["new.py"]


def test_run_batch_runs_all_kinds(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    _run_batch(session, _fake_run(calls), ["x.py"])

    for kind in ("lint", "typecheck", "test"):
        assert latest(session, kind)["origin"] == "watcher"
        assert latest(session, kind)["changed_files"] == ["x.py"]


def test_empty_project(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    lint_calls: list = []

    assert commands(session)["lint"] == []
    assert latest(session)["results"] is None

    entry = lint(tmp_path, "s1", run=_fake_run(lint_calls))

    assert entry["origin"] == "none"
    assert entry["note"] == "no lint commands detected for project"
    assert calls == []
    assert lint_calls == []


def test_latest_default_entry_has_origin_none(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    assert latest(session)["origin"] is None


def test_store_latest_keeps_newer_entry_by_ran_at():
    session = {"latest": {}}
    current = {"kind": "lint", "ran_at": "2020-01-01T00:00:00+00:00"}
    stale = {"kind": "lint", "ran_at": "2019-01-01T00:00:00+00:00"}
    newer = {"kind": "lint", "ran_at": "2021-01-01T00:00:00+00:00"}

    _store_latest(session, current)
    _store_latest(session, stale)

    assert session["latest"]["lint"] is current

    _store_latest(session, newer)

    assert session["latest"]["lint"] is newer


def test_stop_removes_session_and_stops_thread(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    assert get(tmp_path, "s1") is not None
    assert stop(tmp_path, "s1") is True
    assert get(tmp_path, "s1") is None
    assert stop(tmp_path, "s1") is False

    thread = session["thread"]
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_stop_empty_session_id_raises(tmp_path):
    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        stop(tmp_path, "")


def test_lint_without_session_runs_now(tmp_path, monkeypatch):
    monkeypatch.setitem(DETECTORS, "lint", lambda project: [CANNED_LINT_COMMAND])
    calls: list = []

    entry = lint(tmp_path, "s1", run=_fake_run(calls))

    assert entry["ok"] is True
    assert entry["ran_at"] is not None
    assert entry["origin"] == "on-demand"
    assert entry["results"][0]["argv"] == ["ruff", "check"]
    assert calls == [([CANNED_LINT_COMMAND], None)]
    assert get(tmp_path, "s1") is None


def test_lint_without_latest_runs_and_stores(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    monkeypatch.setitem(DETECTORS, "lint", lambda project: [CANNED_LINT_COMMAND])
    lint_calls: list = []

    entry = lint(tmp_path, "s1", run=_fake_run(lint_calls))

    assert entry["ok"] is True
    assert latest(session)["results"] is not None
    assert lint_calls == [([CANNED_LINT_COMMAND], None)]


def test_lint_returns_running_state_when_watcher_in_flight(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    session["running"] = True
    lint_calls: list = []

    entry = lint(tmp_path, "s1", run=_fake_run(lint_calls))

    assert entry["origin"] is None
    assert entry["running"] is True
    assert lint_calls == []


def test_lint_empty_session_id_raises(tmp_path):
    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        lint(tmp_path, "")


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        ("typecheck", CANNED_TYPECHECK_COMMAND),
        ("test", CANNED_TEST_COMMAND),
    ],
    ids=["typecheck", "test"],
)
def test_run_check_without_latest_runs_and_stores(tmp_path, monkeypatch, kind, command):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))

    monkeypatch.setitem(DETECTORS, kind, lambda project: [command])
    check_calls: list = []

    entry = run_check(tmp_path, "s1", kind, run=_fake_run(check_calls))

    assert entry["origin"] == "on-demand"
    assert entry["ok"] is True
    assert check_calls == [([command], None)]
    assert latest(session, kind)["results"] is not None


@pytest.mark.parametrize("kind", ["lint", "typecheck", "test"])
def test_run_check_returns_cached_when_ready(tmp_path, monkeypatch, kind):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_ruff_ty_pytest(tmp_path)
    calls: list = []
    session = start(tmp_path, "s1", run=_fake_run(calls))
    initial = latest(session, kind)
    check_calls: list = []

    entry = run_check(tmp_path, "s1", kind, run=_fake_run(check_calls))

    assert entry == initial
    assert entry["origin"] == "initial"
    assert check_calls == []


@pytest.mark.parametrize("kind", ["typecheck", "test"])
def test_run_check_empty_project(tmp_path, monkeypatch, kind):
    _patch_which(monkeypatch, {"uv"})
    calls: list = []
    start(tmp_path, "s1", run=_fake_run(calls))
    check_calls: list = []

    entry = run_check(tmp_path, "s1", kind, run=_fake_run(check_calls))

    assert entry["origin"] == "none"
    assert entry["note"] == f"no {kind} commands detected for project"
    assert check_calls == []
