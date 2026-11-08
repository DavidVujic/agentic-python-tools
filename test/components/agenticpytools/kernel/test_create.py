"""Unit tests for kernelspec creation helpers."""

from types import SimpleNamespace
from typing import cast

import pytest
from agenticpytools.kernel import create
from jupyter_client.kernelspec import KernelSpecManager

pytestmark = pytest.mark.kernel


class FakeKSM:
    def __init__(self, specs):
        self.specs = specs
        self.calls = []

    def get_all_specs(self):
        return self.specs

    def install_kernel_spec(self, source_dir, kernel_name, user):
        self.calls.append((source_dir, kernel_name, user))


def test_installed_argv():
    ksm = SimpleNamespace(get_all_specs=lambda: {"k": {"spec": {"argv": ["a"]}}})
    assert create.installed_argv(cast(KernelSpecManager, ksm), "k") == ["a"]

    empty = SimpleNamespace(get_all_specs=dict)
    assert create.installed_argv(cast(KernelSpecManager, empty), "k") is None


def test_ensure_project_spec_noop_when_matching(monkeypatch):
    ksm = FakeKSM({"k": {"spec": {"argv": ["a"]}}})
    monkeypatch.setattr(create, "KernelSpecManager", lambda: ksm)

    create.ensure_project_spec("k", ["a"])

    assert ksm.calls == []


def test_ensure_project_spec_installs_when_missing(monkeypatch):
    ksm = FakeKSM({})
    monkeypatch.setattr(create, "KernelSpecManager", lambda: ksm)

    create.ensure_project_spec("k", ["a"])

    assert len(ksm.calls) == 1
    _, kernel_name, user = ksm.calls[0]
    assert kernel_name == "k"
    assert user is True


def test_ensure_project_spec_installs_when_argv_differs(monkeypatch):
    ksm = FakeKSM({"k": {"spec": {"argv": ["old"]}}})
    monkeypatch.setattr(create, "KernelSpecManager", lambda: ksm)

    create.ensure_project_spec("k", ["new"])

    assert len(ksm.calls) == 1


def test_create_kernel_manager(monkeypatch):
    monkeypatch.setattr(create, "get_transport", lambda: "ipc")

    km = create.create_kernel_manager("k", "cf.json")

    assert km.kernel_name == "k"
    assert km.transport == "ipc"
