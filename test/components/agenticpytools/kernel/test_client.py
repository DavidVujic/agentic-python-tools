"""Unit tests for the kernel client close flow."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from agenticpytools.kernel import client

pytestmark = pytest.mark.kernel


def _isolated(monkeypatch, stored):
    calls = {"shutdown": [], "deleted": []}
    monkeypatch.setattr(
        client,
        "storage",
        SimpleNamespace(
            load_entry=lambda _: stored,
            delete_entry=lambda name: calls["deleted"].append(name),
        ),
    )
    monkeypatch.setattr(
        client, "shutdown_adopted", lambda cf: calls["shutdown"].append(cf)
    )
    monkeypatch.setattr(client, "get_kernel_name", lambda _: "k1")
    return calls


def test_close_not_running(monkeypatch, capsys):
    calls = _isolated(monkeypatch, None)

    client.close(Path("/proj"))

    assert "not running" in capsys.readouterr().out
    assert calls["shutdown"] == []
    assert calls["deleted"] == []


def test_close_running(monkeypatch):
    calls = _isolated(monkeypatch, {"connection_file": "/tmp/cf.json"})

    client.close(Path("/proj"))

    assert calls["shutdown"] == ["/tmp/cf.json"]
    assert calls["deleted"] == ["k1"]
