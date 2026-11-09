"""Unit tests for session-scoped kernel creation and close."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from agenticpytools import storage
from agenticpytools.kernel import client
from agenticpytools.kernel.core import get_session_kernel_name
from agenticpytools.storage import connection

pytestmark = pytest.mark.kernel


class FakeKC:
    """Always-alive kernel client that only records its connection file."""

    def __init__(self, connection_file=None):
        self.connection_file = connection_file

    def load_connection_file(self, connection_file):
        self.connection_file = connection_file

    def start_channels(self):
        pass

    def wait_for_ready(self, timeout):
        pass

    def is_alive(self):
        return True

    def stop_channels(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated DB and fake kernels; each start records a new connection file."""
    project = (tmp_path / "proj").resolve()
    project.mkdir()
    starts = []

    def start(_project):
        cf = tmp_path / f"kernel-{len(starts)}.json"
        cf.write_text("{}")
        starts.append(cf)

        return SimpleNamespace(client=lambda: FakeKC(str(cf)))

    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "kernels.db")
    monkeypatch.setattr(client, "create_and_start_kernel", start)
    monkeypatch.setattr(client, "shutdown_adopted", lambda cf: Path(cf).unlink())
    monkeypatch.setattr(client, "BlockingKernelClient", FakeKC)

    return SimpleNamespace(project=project, path=str(project), starts=starts)


def _entry(env, session_id):
    return storage.load_entry(get_session_kernel_name(env.project, session_id))


def test_sessions_get_separate_kernels_and_reuse_their_own(env):
    first = client.create(env.path, "a", 1)
    other = client.create(env.path, "b", 1)
    again = client.create(env.path, "a", 1)

    assert len(env.starts) == 2
    assert first.connection_file != other.connection_file
    assert again.connection_file == first.connection_file


def test_close_only_closes_that_session(env, capsys):
    client.create(env.path, "a", 1)
    client.create(env.path, "b", 1)
    closed = _entry(env, "a")["connection_file"]

    client.close(env.project, "a")

    assert not Path(closed).exists()
    assert _entry(env, "a") is None
    assert Path(_entry(env, "b")["connection_file"]).exists()

    client.close(env.project, "a")

    assert "not running" in capsys.readouterr().out
