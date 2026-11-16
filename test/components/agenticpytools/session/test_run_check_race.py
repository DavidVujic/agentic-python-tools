"""Unit tests for on-demand checks racing a session stop or replacement."""

from threading import Event, Thread

import pytest
from agenticpytools.session import get, run_check, start, stop
from agenticpytools.session.core import DETECTORS

pytestmark = pytest.mark.session

STALE_COMMAND = {"argv": ["ruff", "check"]}
FRESH_COMMAND = {"argv": ["ruff", "check", "--fresh"]}


def _fake_run(calls: list):
    def run(commands, files=None, timeout=60.0):
        calls.append((commands, files))

        return [
            {"argv": c["argv"], "returncode": 0, "stdout": "", "stderr": ""}
            for c in commands
        ]

    return run


def _no_commands(project):
    return []


def _detect_in_order(responses: list, detecting: Event, proceed: Event):
    """A detector returning the responses in order; the first call blocks until released."""
    pending = list(responses)

    def detect(project):
        response = pending.pop(0)

        if len(pending) == len(responses) - 1:
            detecting.set()
            proceed.wait(timeout=5)

        return response

    return detect, pending


def _start_and_wait(project, session_id: str) -> dict:
    session = start(project, session_id, run=_fake_run([]))

    assert session["initial_done"].wait(timeout=5)

    return session


def _untouched(session: dict) -> bool:
    return session["latest"] == {} and session["pending"]["lint"] == 0


@pytest.mark.parametrize("replace", [False, True], ids=["stopped", "replaced"])
@pytest.mark.parametrize("fresh", [[FRESH_COMMAND], []], ids=["fresh", "none"])
def test_run_check_stopped_during_detection_redetects_uncached(
    tmp_path, monkeypatch, replace, fresh
):
    for kind in DETECTORS:
        monkeypatch.setitem(DETECTORS, kind, _no_commands)

    old = _start_and_wait(tmp_path, "s1")
    detecting, proceed = Event(), Event()
    replacement_detection = [[]] if replace else []
    detect, pending = _detect_in_order(
        [[STALE_COMMAND], *replacement_detection, fresh], detecting, proceed
    )
    monkeypatch.setitem(DETECTORS, "lint", detect)
    check_calls: list = []
    returned: list = []
    worker = Thread(
        target=lambda: returned.append(
            run_check(tmp_path, "s1", "lint", run=_fake_run(check_calls))
        )
    )

    try:
        worker.start()

        assert detecting.wait(timeout=5)
        assert stop(tmp_path, "s1") is True

        current = _start_and_wait(tmp_path, "s1") if replace else None
        proceed.set()
        worker.join(timeout=5)
        [entry] = returned

        assert pending == []
        assert entry["running"] is False
        assert entry["origin"] == ("on-demand" if fresh else "none")
        assert check_calls == ([(fresh, None)] if fresh else [])
        assert get(tmp_path, "s1") is current
        assert _untouched(old)
        assert current is None or _untouched(current)
    finally:
        proceed.set()
        worker.join(timeout=5)
        stop(tmp_path, "s1")
