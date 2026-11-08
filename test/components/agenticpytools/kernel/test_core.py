"""Unit tests for the kernel component core functions."""

import hashlib
import os
from pathlib import Path

import pytest
from agenticpytools.kernel import core

pytestmark = pytest.mark.kernel


def test_get_kernel_name():
    project = Path("/x/myproj")
    expected = "repl-myproj-" + hashlib.sha256(b"/x/myproj").hexdigest()[:8]

    assert core.get_kernel_name(project) == expected
    assert core.get_kernel_name(project) == expected
    assert core.get_kernel_name(Path("/x/other")) != expected


def test_get_transport(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    assert core.get_transport() == "tcp"

    monkeypatch.setattr(os, "name", "posix")
    assert core.get_transport() == "ipc"


def test_get_connection_file_path(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jupyter_runtime_dir", lambda: str(tmp_path))

    assert core.get_connection_file_path("abc") == tmp_path / "kernel-abc.json"


def test_spec_data():
    assert core.spec_data(["a"], "k") == {
        "argv": ["a"],
        "display_name": "Python REPL (k)",
        "language": "python",
    }


def _dist_info(project: Path, name: str) -> None:
    dist_info = (
        project
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / f"{name}-7.4.0.dist-info"
    )
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Name: {name}\n")


def test_venv_has_ipykernel_without_venv(tmp_path):
    assert core.venv_has_ipykernel(tmp_path) is False


def test_venv_has_ipykernel_without_lib(tmp_path):
    (tmp_path / ".venv").mkdir()

    assert core.venv_has_ipykernel(tmp_path) is False


def test_venv_has_ipykernel_installed(tmp_path):
    _dist_info(tmp_path, "ipykernel")

    assert core.venv_has_ipykernel(tmp_path) is True


def test_venv_has_ipykernel_other_package(tmp_path):
    _dist_info(tmp_path, "other")

    assert core.venv_has_ipykernel(tmp_path) is False


def test_kernel_argv_uv(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "is_uv", lambda _: True)

    assert core.kernel_argv(tmp_path) == [
        "uv",
        "run",
        "--project",
        str(tmp_path),
        "--with",
        "ipykernel",
        "python",
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]


def test_kernel_argv_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "is_uv", lambda _: False)
    monkeypatch.setattr(core, "venv_has_ipykernel", lambda _: True)
    python = Path("/p/.venv/bin/python")
    monkeypatch.setattr(core, "venv_python", lambda _: python)

    assert core.kernel_argv(tmp_path) == [
        str(python),
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]


def test_kernel_argv_without_ipykernel(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "is_uv", lambda _: False)
    monkeypatch.setattr(core, "venv_has_ipykernel", lambda _: False)

    with pytest.raises(RuntimeError):
        core.kernel_argv(tmp_path)
