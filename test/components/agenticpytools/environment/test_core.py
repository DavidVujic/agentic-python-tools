"""Unit tests for the environment component."""

import os
from pathlib import Path

import pytest
from agenticpytools.environment.core import (
    expected_venv_python,
    is_uv,
    is_windows,
    venv_dir,
    venv_python,
    windows_venv,
)

pytestmark = pytest.mark.environment


def test_is_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    assert is_windows() is True

    monkeypatch.setattr(os, "name", "posix")
    assert is_windows() is False


def test_windows_venv():
    assert windows_venv(Path("/p")) == Path("/p/Scripts/python.exe")


def test_expected_venv_python(monkeypatch):
    venv = Path("/p/.venv")

    monkeypatch.setattr(os, "name", "nt")
    assert expected_venv_python(venv) == venv / "Scripts" / "python.exe"

    monkeypatch.setattr(os, "name", "posix")
    assert expected_venv_python(venv) == venv / "bin" / "python"


def test_venv_dir():
    assert venv_dir("/proj") == Path("/proj/.venv")


def test_venv_python_found(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    python = venv_dir(tmp_path) / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    expected = Path(tmp_path).expanduser().resolve() / ".venv" / "bin" / "python"

    assert venv_python(tmp_path) == expected


def test_venv_python_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        venv_python(tmp_path)


def test_is_uv(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.core.shutil.which", lambda _: "/usr/bin/uv"
    )

    assert is_uv(tmp_path) is False

    (tmp_path / "uv.lock").touch()
    assert is_uv(tmp_path) is True

    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", lambda _: None)
    assert is_uv(tmp_path) is False
