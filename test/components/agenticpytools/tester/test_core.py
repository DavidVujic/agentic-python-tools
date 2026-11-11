"""Unit tests for test command detection."""

from pathlib import Path

import pytest
from agenticpytools.tester.core import detect_test_commands

pytestmark = pytest.mark.tester


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def test_justfile_wins_over_makefile(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("test:\n    pytest\n")
    (tmp_path / "Makefile").write_text("test:\n\tpytest\n")

    commands = detect_test_commands(tmp_path)

    assert commands == [
        {
            "argv": ["just", "test"],
            "cwd": str(Path(tmp_path).resolve()),
            "source": "justfile",
            "tool": "just",
        }
    ]


def test_makefile_when_justfile_has_no_test_recipe(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("lint:\n    ruff check .\n")
    (tmp_path / "Makefile").write_text("test:\n\tpytest\n")

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["make", "test"]]


def test_justfile_tests_recipe(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just"})
    (tmp_path / "justfile").write_text("tests:\n    pytest\n")

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["just", "tests"]]


def test_uv_project_with_pytest_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["pytest"]\n')

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "pytest"]]
    assert commands[0]["source"] == "pyproject"


def test_pytest_config_marker_with_uv_prefix(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "pytest"]]
    assert commands[0]["source"] == "config-file"


def test_tox_ini_marker(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    (tmp_path / "tox.ini").write_text("[testenv]\n")

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["tox"]]
    assert commands[0]["source"] == "config-file"


def test_poe_task_in_uv_project(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[tool.poe.tasks]\ntest = "pytest"\n')

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "poe", "test"]]


def test_pixi_task(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"pixi"})
    (tmp_path / "pyproject.toml").write_text('[tool.pixi.tasks]\ntest = "pytest"\n')

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["pixi", "run", "test"]]


def test_hatch_env_script(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"hatch"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.hatch.envs.test.scripts]\ntest = "pytest"\n'
    )

    commands = detect_test_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["hatch", "run", "test:test"]]


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
        / "pytest-8.0.0.dist-info"
    )
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text("Name: pytest\n")

    commands = detect_test_commands(tmp_path)

    expected_python = str(Path(tmp_path).resolve() / ".venv" / "bin" / "python")
    assert [c["argv"] for c in commands] == [[expected_python, "-m", "pytest"]]
    assert commands[0]["source"] == "venv"


def test_invalid_toml_skips_pyproject_sources(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "poe", "pixi", "hatch"})
    (tmp_path / "pyproject.toml").write_text("[tool.uv\n")

    assert detect_test_commands(tmp_path) == []


def test_no_test_commands(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "just", "make", "poe", "pixi", "hatch"})

    assert detect_test_commands(tmp_path) == []
