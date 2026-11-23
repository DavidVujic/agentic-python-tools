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


def _write(project: Path, rel_path: str, content: str) -> None:
    """Write a file under the project, creating missing parent directories."""
    path = project / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _uv_project(project: Path) -> None:
    """A uv project whose dev group depends on ruff, ty, and pytest."""
    (project / "uv.lock").touch()

    _write(
        project,
        "pyproject.toml",
        '[dependency-groups]\ndev = ["ruff", "ty", "pytest"]\n',
    )


def _patch_uv(monkeypatch) -> None:
    """Make both shutil.which sites find uv and nothing else."""

    def which(name: str) -> str | None:
        return "/usr/bin/uv" if name == "uv" else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _patch_uv_just(monkeypatch) -> None:
    """Make both shutil.which sites find uv and just, and nothing else."""

    def which(name: str) -> str | None:
        return "/usr/bin/" + name if name in {"uv", "just"} else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _patch_just(monkeypatch) -> None:
    """Make both shutil.which sites find just and nothing else."""

    def which(name: str) -> str | None:
        return "/usr/bin/just" if name == "just" else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _results(commands: list[dict]) -> list[dict]:
    """Successful results for the given commands."""
    return [
        {"argv": c["argv"], "returncode": 0, "stdout": "", "stderr": ""}
        for c in commands
    ]


def _fake_run(calls: list):
    """A run that records its calls and succeeds for every command."""

    def run(commands, files=None, _timeout=60.0):
        calls.append((commands, files))

        return _results(commands)

    return run


def _wait_until(condition, timeout: float = 5.0) -> bool:
    """Poll a condition until it holds or the timeout passes."""
    deadline = monotonic() + timeout

    while monotonic() < deadline:
        if condition():
            return True

        sleep(0.05)

    return False


def _initial_done(session: dict) -> bool:
    """True while no run of any kind is scheduled or in progress."""
    return not any(latest(session, kind)["running"] for kind in KINDS)


def _start_and_wait(project: Path, session_id: str, run) -> dict:
    """Start a session and wait until its initial background runs finish."""
    session = start(project, session_id, run=run)

    assert _wait_until(lambda: _initial_done(session)), "initial runs did not finish"

    return session


def _batch_session(project: Path) -> dict:
    """A minimal session with one canned command per kind."""
    return {
        "project": str(project),
        "commands": {
            kind: {"all": [CANNED_LINT_COMMAND], "files": []} for kind in KINDS
        },
        "latest": {},
        "pending": dict.fromkeys(KINDS, 0),
        "stop": Event(),
    }


def _run_batch_collecting(session: dict, batch, kinds=None):
    """Run one batch through a recording fake run; return (session, calls)."""
    calls: list = []
    pending = kinds if kinds is not None else _mark_pending(session)

    _run_batch(session, _fake_run(calls), batch, pending)

    return session, calls


def _pkg_project(tmp_path: Path, test_name: str, test_body: str) -> None:
    """Scaffold a pkg module and one test file importing it."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, f"test/{test_name}", test_body)


def _record_argvs(monkeypatch) -> list:
    """Record every subprocess argv and report a successful, silent run."""
    argvs: list = []

    def fake_run(argv, **_kwargs):
        argvs.append(argv)

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("agenticpytools.runner.core.subprocess.run", fake_run)

    return argvs


def _assert_changed_files(session: dict, batch: list[str]) -> None:
    """Assert every kind's latest entry ran on the batch's files."""
    for kind in KINDS:
        assert session["latest"][kind]["changed_files"] == batch


def test_run_batch_runs_all_kinds(tmp_path, monkeypatch):
    _patch_uv(monkeypatch)
    _uv_project(tmp_path)
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
    session, calls = _run_batch_collecting(session, ["gone.py", "kept.py"])

    files_seen = [files for _, files in calls]

    assert files_seen.count(["kept.py"]) == 2
    assert files_seen.count(None) == 1
    _assert_changed_files(session, ["gone.py", "kept.py"])


def test_run_batch_runs_whole_project_when_all_deleted(tmp_path):
    session = _batch_session(tmp_path)
    session, calls = _run_batch_collecting(session, ["gone.py"])

    assert [files for _, files in calls] == [None] * len(KINDS)

    for kind in KINDS:
        assert session["latest"][kind]["origin"] == "watcher"

    _assert_changed_files(session, ["gone.py"])


def test_run_batch_runs_affected_tests_on_production_file_change(tmp_path, monkeypatch):
    _patch_uv(monkeypatch)
    _uv_project(tmp_path)
    _pkg_project(tmp_path, "test_module.py", "from pkg import module\n")
    argvs = _record_argvs(monkeypatch)

    session = _batch_session(tmp_path)
    session["commands"] = {kind: DETECTORS[kind](tmp_path) for kind in KINDS}

    _run_batch(session, run_commands, ["pkg/module.py"], _mark_pending(session))

    pytest_argvs = [argv for argv in argvs if argv[:3] == ["uv", "run", "pytest"]]
    assert pytest_argvs == [["uv", "run", "pytest", "test/test_module.py"]]
    assert ["uv", "run", "ruff", "check", "pkg/module.py"] in argvs
    assert ["uv", "run", "ty", "check", "pkg/module.py"] in argvs
    assert session["latest"]["test"]["changed_files"] == ["pkg/module.py"]


def test_run_batch_justfile_project_runs_the_file_scoped_commands(
    tmp_path, monkeypatch
):
    _patch_uv_just(monkeypatch)
    _uv_project(tmp_path)
    _write(
        tmp_path,
        "justfile",
        "lint:\n    uv run ruff check\n\ntypecheck:\n    uv run ty check"
        "\n\ntest:\n    uv run pytest\n",
    )
    _pkg_project(tmp_path, "test_module.py", "from pkg import module\n")
    argvs = _record_argvs(monkeypatch)

    session = _batch_session(tmp_path)
    session["commands"] = {kind: DETECTORS[kind](tmp_path) for kind in KINDS}

    _run_batch(session, run_commands, ["pkg/module.py"], _mark_pending(session))

    pytest_argvs = [argv for argv in argvs if argv[:3] == ["uv", "run", "pytest"]]

    assert not any(argv[0] == "just" for argv in argvs)
    assert pytest_argvs == [["uv", "run", "pytest", "test/test_module.py"]]
    assert session["latest"]["test"]["scope"] == "files"
    assert session["latest"]["lint"]["scope"] == "files"
    assert session["latest"]["typecheck"]["scope"] == "files"


def test_run_batch_justfile_only_project_falls_back_to_the_full_command(
    tmp_path, monkeypatch
):
    _patch_just(monkeypatch)
    (tmp_path / "justfile").write_text("test:\n    pytest\n")
    _pkg_project(tmp_path, "test_module.py", "from pkg import module\n")
    argvs = _record_argvs(monkeypatch)

    session = _batch_session(tmp_path)
    session["commands"] = {kind: DETECTORS[kind](tmp_path) for kind in KINDS}

    assert session["commands"]["test"]["files"] == []

    _run_batch(session, run_commands, ["pkg/module.py"], _mark_pending(session))

    assert argvs == [["just", "test"]]
    assert session["latest"]["test"]["scope"] == "all"


def test_run_batch_lint_uses_the_file_scoped_ruff_commands(tmp_path, monkeypatch):
    _patch_uv_just(monkeypatch)
    (tmp_path / "uv.lock").touch()
    _write(tmp_path, "pyproject.toml", '[dependency-groups]\ndev = ["ruff"]\n')
    _write(tmp_path, "justfile", "lint:\n    uv run ruff check\n")
    _write(tmp_path, "new.py", "x = 1\n")
    argvs = _record_argvs(monkeypatch)

    session = _batch_session(tmp_path)
    session["commands"] = {kind: DETECTORS[kind](tmp_path) for kind in KINDS}

    _run_batch(session, run_commands, ["new.py"], _mark_pending(session))

    assert argvs == [
        ["uv", "run", "ruff", "check", "new.py"],
        ["uv", "run", "ruff", "format", "--check", "new.py"],
    ]
    assert session["latest"]["lint"]["scope"] == "files"


def test_run_batch_publishes_note_when_no_test_is_affected(tmp_path):
    _pkg_project(
        tmp_path, "test_unrelated.py", "def test_unrelated():\n    assert True\n"
    )

    session = _batch_session(tmp_path)
    session["commands"] = {
        kind: {"all": [{"argv": [tool]}], "files": []}
        for kind, tool in zip(KINDS, ("ruff", "ty", "pytest"))
    }
    session, calls = _run_batch_collecting(session, ["pkg/module.py"])

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

    session, calls = _run_batch_collecting(session, None, KINDS)

    assert calls == []
    assert _mark_pending(session) == ()
    for kind in KINDS:
        entry = latest(session, kind)

        assert entry["origin"] == "initial"
        assert entry["results"] is None
        assert entry["ok"] is None
        assert entry["note"] == f"{kind} run cancelled: session stopped"
        assert entry["running"] is False
