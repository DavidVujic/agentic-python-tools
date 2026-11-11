"""Unit tests for type check command detection."""

from pathlib import Path

import pytest
from agenticpytools.typechecker.core import detect_typecheck_commands

pytestmark = pytest.mark.typechecker


def _patch_which(monkeypatch, found: set[str]) -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in found else None

    monkeypatch.setattr("agenticpytools.checks.sources.shutil.which", which)
    monkeypatch.setattr("agenticpytools.environment.core.shutil.which", which)


def test_uv_project_with_ty_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["ty"]\n')

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "ty", "check"]]


def test_uv_project_with_mypy_section(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\n")

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "mypy", "."]]


def test_uv_project_with_pyright_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["Pyright>=1"]\n'
    )

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "pyright"]]


def test_justfile_wins_over_makefile(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("typecheck:\n    ty check .\n")
    (tmp_path / "Makefile").write_text("type-check:\n\tmypy .\n")

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["just", "typecheck"]]


def test_makefile_when_justfile_has_no_typecheck_recipe(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("lint:\n    ruff check .\n")
    (tmp_path / "Makefile").write_text("types:\n\tpython -m mypy .\n")

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["make", "types"]]


def test_poe_task_in_uv_project(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poe.tasks]\ntypecheck = "ty check ."\n'
    )

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["uv", "run", "poe", "typecheck"]]


def test_hatch_env_script(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"hatch"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.hatch.envs.test.scripts]\ntype-check = "ty check ."\n'
    )

    commands = detect_typecheck_commands(tmp_path)

    assert [c["argv"] for c in commands] == [["hatch", "run", "test:type-check"]]


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
        / "ty-0.0.1.dist-info"
    )
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text("Name: ty\n")

    commands = detect_typecheck_commands(tmp_path)

    expected_python = str(Path(tmp_path).resolve() / ".venv" / "bin" / "python")
    assert [c["argv"] for c in commands] == [[expected_python, "-m", "ty", "check"]]
    assert commands[0]["source"] == "venv"


def test_no_typecheck_commands(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "just", "make", "poe", "pixi", "hatch"})

    assert detect_typecheck_commands(tmp_path) == []
