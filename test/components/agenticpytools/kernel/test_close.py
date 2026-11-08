"""Unit tests for adopted-kernel shutdown."""

import pytest
from agenticpytools.kernel import close as close_mod

pytestmark = pytest.mark.kernel


class FakeClient:
    def __init__(self):
        self.loaded = None
        self.shutdown_called = False
        self.channels_stopped = False

    def load_connection_file(self, path):
        self.loaded = path

    def start_channels(self):
        pass

    def shutdown(self):
        self.shutdown_called = True

    def is_alive(self):
        return False

    def stop_channels(self):
        self.channels_stopped = True


def test_shutdown_adopted_missing_file(tmp_path):
    close_mod.shutdown_adopted(str(tmp_path / "nope.json"))


def test_shutdown_adopted_cleans_up(tmp_path, monkeypatch):
    instances = []

    def fake_client():
        client = FakeClient()
        instances.append(client)
        return client

    monkeypatch.setattr(close_mod, "BlockingKernelClient", fake_client)

    connection_file = tmp_path / "kernel-x.json"
    connection_file.write_text("{}")
    ipc_1 = tmp_path / "kernel-x-ipc-1"
    ipc_2 = tmp_path / "kernel-x-ipc-2"
    ipc_1.touch()
    ipc_2.touch()

    close_mod.shutdown_adopted(str(connection_file))

    assert len(instances) == 1
    assert instances[0].loaded == str(connection_file)
    assert instances[0].shutdown_called is True
    assert instances[0].channels_stopped is True
    assert not connection_file.exists()
    assert not ipc_1.exists()
    assert not ipc_2.exists()
