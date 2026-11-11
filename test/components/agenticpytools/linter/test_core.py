"""Unit tests for lint command detection."""

from pathlib import Path

import pytest
from agenticpytools.linter.core import detect_lint_commands

pytestmark = pytest.mark.linter


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def test_justfile_wins_over_makefile(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("lint:\n    ruff check .\n")
    (tmp_path / "Makefile").write_text("lint:\n\truff check .\n")

    commands = detect_lint_commands(tmp_path)

    assert commands == [
        {
            "argv": ["just", "lint"],
            "cwd": str(Path(tmp_path).resolve()),
            "source": "justfile",
            "tool": "just",
        }
    ]


def test_makefile_when_justfile_has_no_lint_recipe(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("test:\n    pytest\n")
    (tmp_path / "Makefile").write_text("lint:\n\truff check .\n")

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["make", "lint"]]


def test_uv_project_with_ruff_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["ruff"]\n')

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [
        ["uv", "run", "ruff", "check"],
        ["uv", "run", "ruff", "format", "--check"],
    ]


def test_uv_project_with_flake8_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["flake8"]\n')

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "flake8"]]


def test_poe_task(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"poe"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poe.tasks]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["poe", "lint"]]


def test_pixi_task(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"pixi"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pixi.tasks]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["pixi", "run", "lint"]]


def test_hatch_env_script(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"hatch"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.hatch.envs.test.scripts]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["hatch", "run", "test:lint"]]


def test_config_file_marker(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    (tmp_path / ".flake8").touch()

    commands = detect_lint_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["flake8"]]
    assert commands[0]["source"] == "config-file"


def test_invalid_toml_skips_pyproject_sources(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "poe", "pixi", "hatch"})
    (tmp_path / "pyproject.toml").write_text("[tool.uv\n")

    assert detect_lint_commands(tmp_path) == []


def test_venv_fallback(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    dist_info = (
        tmp_path
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "flake8-7.0.0.dist-info"
    )
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text("Name: flake8\n")

    commands = detect_lint_commands(tmp_path)

    expected_python = str(Path(tmp_path).resolve() / ".venv" / "bin" / "python")
    assert [c["argv"] for c in commands] == [[expected_python, "-m", "flake8"]]
    assert commands[0]["source"] == "venv"


def test_no_lint_commands(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "just", "make", "poe", "pixi", "hatch"})

    assert detect_lint_commands(tmp_path) == []
