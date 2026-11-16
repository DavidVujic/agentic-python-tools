"""Unit tests for debounced batches of changed Python files."""

import sys
from queue import Queue
from threading import Thread
from time import sleep

import pytest
from agenticpytools.watcher import changed_python_files
from agenticpytools.watcher.core import _is_ignored

pytestmark = pytest.mark.watcher


def test_is_ignored(tmp_path):
    assert _is_ignored(tmp_path / ".venv" / "x.py", tmp_path)
    assert not _is_ignored(tmp_path / "src" / "x.py", tmp_path)
    assert _is_ignored(tmp_path / ".git", tmp_path)
    assert _is_ignored(tmp_path / "build.egg-info", tmp_path)
    assert not _is_ignored(tmp_path / "package" / "mod.py", tmp_path)


def test_changed_python_files_yields_new_file(tmp_path):
    batches: Queue[list[str]] = Queue()

    def run():
        for batch in changed_python_files(tmp_path, debounce=0.1):
            batches.put(batch)

    Thread(target=run, daemon=True).start()
    sleep(0.2)
    (tmp_path / "new.py").write_text("x = 1")

    assert "new.py" in batches.get(timeout=5)


def test_changed_python_files_requires_watchfiles(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "watchfiles", None)

    with pytest.raises(ImportError):
        next(changed_python_files(tmp_path))
