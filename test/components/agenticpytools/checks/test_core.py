"""Unit tests for the two-scope command detection."""

from pathlib import Path

import pytest
from agenticpytools.checks import detect_commands
from agenticpytools.checks.tools import Tool

pytestmark = pytest.mark.checks

TEST_TOOLS: dict[str, Tool] = {
    "pytest": {
        "argvs": [[]],
        "sections": ["tool.pytest.ini_options"],
        "ini_sections": ["pytest", "tool:pytest"],
        "files": ["pytest.ini"],
        "takes_files": True,
    },
}
RECIPE_NAMES = ("test", "tests")


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def _uv_project_with_pytest(project: Path) -> None:
    """A uv project whose dev group depends on pytest."""
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text('[dependency-groups]\ndev = ["pytest"]\n')


def _justfile_test_recipe(project: Path) -> None:
    (project / "justfile").write_text("test:\n    pytest\n")


def test_justfile_all_with_pyproject_pytest_files(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "uv"})
    _uv_project_with_pytest(tmp_path)
    _justfile_test_recipe(tmp_path)

    detected = detect_commands(tmp_path, TEST_TOOLS, RECIPE_NAMES)

    assert detected["all"] == [
        {
            "argv": ["just", "test"],
            "cwd": str(Path(tmp_path).resolve()),
            "source": "justfile",
            "tool": "just",
        }
    ]
    assert detected["files"] == [
        {
            "argv": ["uv", "run", "pytest"],
            "cwd": str(Path(tmp_path).resolve()),
            "source": "pyproject",
            "tool": "pytest",
            "takes_files": True,
        }
    ]


def test_pyproject_only_filters_all_for_files(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    _uv_project_with_pytest(tmp_path)

    detected = detect_commands(tmp_path, TEST_TOOLS, RECIPE_NAMES)

    assert detected["files"] == [c for c in detected["all"] if c.get("takes_files")]


def test_justfile_without_deeper_source_has_empty_files(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just"})
    _justfile_test_recipe(tmp_path)

    detected = detect_commands(tmp_path, TEST_TOOLS, RECIPE_NAMES)

    assert [c["argv"] for c in detected["all"]] == [["just", "test"]]
    assert detected["files"] == []


def test_empty_project_detects_no_commands(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make", "uv", "poe", "pixi", "hatch"})

    detected = detect_commands(tmp_path, TEST_TOOLS, RECIPE_NAMES)

    assert detected == {"all": [], "files": []}
