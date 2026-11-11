"""Unit tests for the environment component's project-tool detection."""

import pytest
from agenticpytools.environment.tools import project_tool

pytestmark = pytest.mark.environment


def test_project_tool_uv(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which", lambda _: "/usr/bin/uv"
    )
    (tmp_path / "uv.lock").touch()

    assert project_tool(tmp_path) == {
        "tool": "uv",
        "prefix": ["uv", "run"],
        "source": "uv.lock",
    }


def test_project_tool_poetry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which", lambda _: "/usr/bin/poetry"
    )
    (tmp_path / "poetry.lock").touch()

    assert project_tool(tmp_path) == {
        "tool": "poetry",
        "prefix": ["poetry", "run"],
        "source": "poetry.lock",
    }


def test_project_tool_priority(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which", lambda _: "/usr/bin/tool"
    )
    (tmp_path / "uv.lock").touch()
    (tmp_path / "poetry.lock").touch()

    assert project_tool(tmp_path) == {
        "tool": "uv",
        "prefix": ["uv", "run"],
        "source": "uv.lock",
    }


def test_project_tool_falls_through_to_next_row(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which",
        lambda name: None if name == "uv" else f"/usr/bin/{name}",
    )
    (tmp_path / "uv.lock").touch()
    (tmp_path / "poetry.lock").touch()

    assert project_tool(tmp_path) == {
        "tool": "poetry",
        "prefix": ["poetry", "run"],
        "source": "poetry.lock",
    }


def test_project_tool_without_any_binary(tmp_path, monkeypatch):
    monkeypatch.setattr("agenticpytools.environment.tools.shutil.which", lambda _: None)
    (tmp_path / "uv.lock").touch()

    assert project_tool(tmp_path) is None


def test_project_tool_pyproject_section(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which", lambda _: "/usr/bin/hatch"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.hatch]\n")

    assert project_tool(tmp_path) == {
        "tool": "hatch",
        "prefix": ["hatch", "run"],
        "source": "tool.hatch",
    }


def test_project_tool_empty_dir(tmp_path):
    assert project_tool(tmp_path) is None


def test_project_tool_invalid_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agenticpytools.environment.tools.shutil.which", lambda _: "/usr/bin/uv"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.uv")

    assert project_tool(tmp_path) is None
