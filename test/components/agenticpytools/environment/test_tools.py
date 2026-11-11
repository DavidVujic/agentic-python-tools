"""Unit tests for the environment component's project-tool detection."""

import pytest
from agenticpytools.environment.tools import project_tool

pytestmark = pytest.mark.environment


def _patch_which(monkeypatch, func):
    """Replace shutil.which in the tools module with func."""
    monkeypatch.setattr("agenticpytools.environment.tools.shutil.which", func)


def _write_files(tmp_path, files):
    """Write files into tmp_path; empty content creates an empty file."""
    for name, content in files.items():
        (tmp_path / name).write_text(content)


CASES = [
    (
        "uv",
        {"uv.lock": ""},
        lambda _: "/usr/bin/uv",
        {"tool": "uv", "prefix": ["uv", "run"], "source": "uv.lock"},
    ),
    (
        "poetry",
        {"poetry.lock": ""},
        lambda _: "/usr/bin/poetry",
        {"tool": "poetry", "prefix": ["poetry", "run"], "source": "poetry.lock"},
    ),
    (
        "priority-uv-wins",
        {"uv.lock": "", "poetry.lock": ""},
        lambda _: "/usr/bin/tool",
        {"tool": "uv", "prefix": ["uv", "run"], "source": "uv.lock"},
    ),
    (
        "falls-through-to-poetry",
        {"uv.lock": "", "poetry.lock": ""},
        lambda name: None if name == "uv" else f"/usr/bin/{name}",
        {"tool": "poetry", "prefix": ["poetry", "run"], "source": "poetry.lock"},
    ),
    (
        "no-binary",
        {"uv.lock": ""},
        lambda _: None,
        None,
    ),
    (
        "hatch-section",
        {"pyproject.toml": "[tool.hatch]\n"},
        lambda _: "/usr/bin/hatch",
        {"tool": "hatch", "prefix": ["hatch", "run"], "source": "tool.hatch"},
    ),
    (
        "invalid-toml",
        {"pyproject.toml": "[tool.uv"},
        lambda _: "/usr/bin/uv",
        None,
    ),
    (
        "empty-dir",
        {},
        lambda _: "/usr/bin/uv",
        None,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_project_tool(tmp_path, monkeypatch, case):
    """project_tool resolves the project's tool from its files and PATH."""
    _, files, which, expected = case
    _write_files(tmp_path, files)
    _patch_which(monkeypatch, which)

    assert project_tool(tmp_path) == expected
