"""Unit tests for the kernel registry."""

import pytest
from agenticpytools.storage import connection, core

pytestmark = pytest.mark.storage


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "kernels.db")


def test_save_and_load_entry():
    core.save_entry("k1", "/tmp/cf.json", "/proj")

    entry = core.load_entry("k1")

    assert entry is not None
    assert entry["kernel_name"] == "k1"
    assert entry["connection_file"] == "/tmp/cf.json"
    assert entry["project_path"] == "/proj"


def test_load_missing_entry():
    assert core.load_entry("nope") is None


def test_save_entry_upserts():
    core.save_entry("k1", "/tmp/one.json", "/proj")
    core.save_entry("k1", "/tmp/two.json", "/proj")

    entry = core.load_entry("k1")

    assert entry is not None
    assert entry["connection_file"] == "/tmp/two.json"
    assert len(core.list_entries()) == 1


def test_delete_entry():
    core.save_entry("k1", "/tmp/cf.json", "/proj")
    core.delete_entry("k1")

    assert core.load_entry("k1") is None


def test_list_entries():
    core.save_entry("a", "/tmp/a.json", "/pa")
    core.save_entry("b", "/tmp/b.json", "/pb")

    names = {entry["kernel_name"] for entry in core.list_entries()}

    assert names == {"a", "b"}
