"""Unit tests for the checks MCP server tools."""

from pathlib import Path
from threading import Event

import pytest
from agenticpytools import session as sessions
from agenticpytools.checks_mcp import core
from agenticpytools.checks_mcp.core import (
    detected_commands,
    lint,
    start_watching,
    stop_watching,
    typecheck,
)
from agenticpytools.session.core import _SESSIONS, DETECTORS, _session_key

pytestmark = pytest.mark.checks_mcp

CANNED_COMMAND = {
    "argv": ["ruff", "check"],
    "cwd": "/p",
    "source": "pyproject",
    "tool": "ruff",
}

CANNED_TYPECHECK_COMMAND = {
    "argv": ["ty", "check"],
    "cwd": "/p",
    "source": "pyproject",
    "tool": "ty",
}

CANNED_TEST_COMMAND = {
    "argv": ["pytest"],
    "cwd": "/p",
    "source": "pyproject",
    "tool": "pytest",
}

CANNED_RESULT = {
    "argv": ["ruff", "check"],
    "returncode": 0,
    "stdout": "",
    "stderr": "",
}

CANNED_LINT_ENTRY = {
    "kind": "lint",
    "results": [CANNED_RESULT],
    "ran_at": "t",
    "changed_files": [],
    "ok": True,
    "origin": "initial",
}

CANNED_TYPECHECK_ENTRY = {
    "kind": "typecheck",
    "results": [CANNED_RESULT],
    "ran_at": "t",
    "changed_files": [],
    "ok": True,
    "origin": "initial",
}

CANNED_TEST_ENTRY = {
    "kind": "test",
    "results": [CANNED_RESULT],
    "ran_at": "t",
    "changed_files": [],
    "ok": True,
    "origin": "initial",
}

CANNED = {
    "project": "/p",
    "session_id": "s1",
    "commands": {
        "lint": [CANNED_COMMAND],
        "typecheck": [CANNED_TYPECHECK_COMMAND],
        "test": [CANNED_TEST_COMMAND],
    },
    "latest": {
        "lint": CANNED_LINT_ENTRY,
        "typecheck": CANNED_TYPECHECK_ENTRY,
        "test": CANNED_TEST_ENTRY,
    },
    "running": False,
    "thread": None,
}


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _fake_run(calls: list):
    def run(commands, files=None, timeout=60.0):
        calls.append((commands, files))

        return [CANNED_RESULT]

    return run


def test_start_watching_returns_metadata_only(monkeypatch):
    monkeypatch.setattr(sessions, "start", lambda project, session_id: CANNED)

    result = start_watching("/p", "s1")

    assert result == {
        "project": "/p",
        "session_id": "s1",
        "watching": True,
        "commands": {
            "lint": [CANNED_COMMAND],
            "typecheck": [CANNED_TYPECHECK_COMMAND],
            "test": [CANNED_TEST_COMMAND],
        },
    }


def test_start_watching_returns_while_initial_runs_are_blocked(tmp_path, monkeypatch):
    entered, release = Event(), Event()

    def blocking_run(commands, files=None, timeout=60.0):
        entered.set()
        release.wait(timeout=5)

        return [CANNED_RESULT]

    monkeypatch.setitem(DETECTORS, "lint", lambda project: [CANNED_COMMAND])
    monkeypatch.setitem(DETECTORS, "typecheck", lambda project: [])
    monkeypatch.setitem(DETECTORS, "test", lambda project: [CANNED_TEST_COMMAND])
    monkeypatch.setattr("agenticpytools.session.core.run_commands", blocking_run)

    try:
        result = start_watching(str(tmp_path), "s1")

        assert entered.wait(timeout=5)
        assert set(result) == {"project", "session_id", "watching", "commands"}
        assert result["watching"] is True
        assert result["commands"]["test"] == [CANNED_TEST_COMMAND]
        assert lint(str(tmp_path), "s1")["running"] is True
    finally:
        release.set()
        stop_watching(str(tmp_path), "s1")


def test_start_watching_error(monkeypatch):
    def boom(project, session_id):
        raise OSError("boom")

    monkeypatch.setattr(sessions, "start", boom)

    assert start_watching("/p", "s1") == {"error": "failed to start watching: boom"}


def test_start_watching_empty_session_id():
    assert start_watching("/p", "") == {
        "error": "session_id must be a non-empty string"
    }


def test_detected_commands_with_session(monkeypatch):
    monkeypatch.setattr(sessions, "get", lambda project, session_id: CANNED)

    assert detected_commands("/p", "s1") == {
        "lint": [CANNED_COMMAND],
        "typecheck": [CANNED_TYPECHECK_COMMAND],
        "test": [CANNED_TEST_COMMAND],
    }


def test_detected_commands_detects_on_demand(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    monkeypatch.setattr(sessions, "get", lambda project, session_id: None)
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["ruff", "ty", "pytest"]\n'
    )

    result = detected_commands(str(tmp_path), "s1")

    assert [c["argv"] for c in result["lint"]] == [
        ["uv", "run", "ruff", "check"],
        ["uv", "run", "ruff", "format", "--check"],
    ]
    assert [c["argv"] for c in result["typecheck"]] == [["uv", "run", "ty", "check"]]
    assert [c["argv"] for c in result["test"]] == [["uv", "run", "pytest"]]
    assert all(
        {"cwd", "source", "tool"} <= set(c)
        for c in [*result["lint"], *result["typecheck"], *result["test"]]
    )


def test_detected_commands_empty_project(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    monkeypatch.setattr(sessions, "get", lambda project, session_id: None)

    assert detected_commands(str(tmp_path), "s1") == {
        "lint": [],
        "typecheck": [],
        "test": [],
    }


def test_detected_commands_error(monkeypatch):
    def boom(project):
        raise OSError("boom")

    monkeypatch.setattr(sessions, "get", lambda project, session_id: None)
    monkeypatch.setattr("agenticpytools.checks_mcp.core.detect_lint_commands", boom)

    assert detected_commands("/p", "s1") == {"error": "failed to detect commands: boom"}


def test_detected_commands_empty_session_id():
    assert detected_commands("/p", "") == {
        "error": "session_id must be a non-empty string"
    }


@pytest.mark.parametrize(
    ("kind", "command", "tool"),
    [
        ("lint", CANNED_COMMAND, lint),
        ("typecheck", CANNED_TYPECHECK_COMMAND, typecheck),
        ("test", CANNED_TEST_COMMAND, core.test),
    ],
    ids=["lint", "typecheck", "test"],
)
def test_tool_runs_on_demand_without_session(monkeypatch, kind, command, tool):
    monkeypatch.setitem(DETECTORS, kind, lambda project: [command])
    calls: list = []
    monkeypatch.setattr("agenticpytools.session.core.run_commands", _fake_run(calls))

    result = tool("/p", "s1")

    assert result["ok"] is True
    assert result["results"] == [CANNED_RESULT]
    assert result["ran_at"] is not None
    assert calls == [([command], None)]


@pytest.mark.parametrize(
    ("entry", "tool"),
    [
        (CANNED_LINT_ENTRY, lint),
        (CANNED_TYPECHECK_ENTRY, typecheck),
        (CANNED_TEST_ENTRY, core.test),
    ],
    ids=["lint", "typecheck", "test"],
)
def test_tool_returns_cached(monkeypatch, entry, tool):
    calls: list = []
    monkeypatch.setattr("agenticpytools.session.core.run_commands", _fake_run(calls))
    monkeypatch.setitem(_SESSIONS, _session_key(Path("/p"), "s1"), CANNED)

    result = tool("/p", "s1")

    assert result == {**entry, "running": False}
    assert result["origin"] == "initial"
    assert calls == []


def test_lint_error(monkeypatch):
    def boom(project, session_id):
        raise OSError("boom")

    monkeypatch.setattr(sessions, "lint", boom)

    assert lint("/p", "s1") == {"error": "failed to run lint: boom"}


def test_typecheck_error(monkeypatch):
    def boom(project, session_id, kind):
        raise OSError("boom")

    monkeypatch.setattr(sessions, "run_check", boom)

    assert typecheck("/p", "s1") == {"error": "failed to run typecheck: boom"}


def test_test_error(monkeypatch):
    def boom(project, session_id, kind):
        raise OSError("boom")

    monkeypatch.setattr(sessions, "run_check", boom)

    assert core.test("/p", "s1") == {"error": "failed to run tests: boom"}


def test_lint_empty_session_id():
    assert lint("/p", "") == {"error": "session_id must be a non-empty string"}


def test_lint_empty_session_id_result_not_shared():
    first = lint("/p", "")
    first["error"] = "changed"

    assert lint("/p", "") == {"error": "session_id must be a non-empty string"}


def test_typecheck_empty_session_id():
    assert typecheck("/p", "") == {"error": "session_id must be a non-empty string"}


def test_test_empty_session_id():
    assert core.test("/p", "") == {"error": "session_id must be a non-empty string"}


def test_stop_watching(monkeypatch):
    monkeypatch.setattr(sessions, "stop", lambda project, session_id: True)

    assert stop_watching("/p", "s1") == {
        "project": "/p",
        "session_id": "s1",
        "stopped": True,
    }


def test_stop_watching_unknown(monkeypatch):
    monkeypatch.setattr(sessions, "stop", lambda project, session_id: False)

    assert stop_watching("/p", "s1") == {
        "error": "no session for this project_full_path/session_id"
    }


def test_stop_watching_empty_session_id():
    assert stop_watching("/p", "") == {"error": "session_id must be a non-empty string"}
