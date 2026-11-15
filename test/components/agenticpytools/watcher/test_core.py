"""Unit tests for debounced batches of changed Python files."""

from queue import Queue
from threading import Thread
from time import sleep

import pytest
from agenticpytools.watcher import changed_python_files
from agenticpytools.watcher.core import _changed, _is_ignored, _poll, _watched_files

pytestmark = pytest.mark.watcher


def test_is_ignored(tmp_path):
    assert _is_ignored(tmp_path / ".venv" / "x.py", tmp_path)
    assert not _is_ignored(tmp_path / "src" / "x.py", tmp_path)
    assert _is_ignored(tmp_path / ".git", tmp_path)
    assert _is_ignored(tmp_path / "build.egg-info", tmp_path)
    assert not _is_ignored(tmp_path / "package" / "mod.py", tmp_path)


def test_watched_files_snapshot(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "a.py").write_text("a = 1")
    (tmp_path / "sub" / "b.py").write_text("b = 2")
    (tmp_path / ".venv" / "c.py").write_text("c = 3")
    (tmp_path / "__pycache__" / "d.py").write_text("d = 4")

    assert set(_watched_files(tmp_path)) == {"a.py", "sub/b.py"}


def test_watched_files_skips_vanished_file(tmp_path):
    (tmp_path / "gone.py").symlink_to(tmp_path / "missing")

    assert "gone.py" not in _watched_files(tmp_path)


def test_changed_detects_new_and_modified():
    before = {"a.py": 1.0, "b.py": 2.0}
    after = {"a.py": 1.5, "b.py": 2.0, "new.py": 3.0}

    assert _changed(before, after) == ["a.py", "new.py"]


def test_changed_unchanged_is_empty():
    before = {"a.py": 1.0}
    after = {"a.py": 1.0}

    assert _changed(before, after) == []


def test_changed_reports_deleted():
    before = {"a.py": 1.0, "gone.py": 2.0}
    after = {"a.py": 1.0}

    assert _changed(before, after) == ["gone.py"]


def test_poll_yields_new_file(tmp_path):
    batches: Queue[list[str]] = Queue()

    def run():
        for batch in _poll(tmp_path, interval=0.05):
            batches.put(batch)

    Thread(target=run, daemon=True).start()
    sleep(0.1)
    (tmp_path / "new.py").write_text("x = 1")

    assert batches.get(timeout=5) == ["new.py"]


def test_changed_python_files_yields_new_file(tmp_path):
    batches: Queue[list[str]] = Queue()

    def run():
        for batch in changed_python_files(tmp_path, debounce=0.1):
            batches.put(batch)

    Thread(target=run, daemon=True).start()
    sleep(0.2)
    (tmp_path / "new.py").write_text("x = 1")

    assert "new.py" in batches.get(timeout=5)


def test_changed_python_files_returns_iterator(tmp_path):
    iterator = changed_python_files(tmp_path)

    assert hasattr(iterator, "__next__")
