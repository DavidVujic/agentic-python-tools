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


def _fake_venv(project: Path, dist: str) -> None:
    """A venv with a Python binary and one installed distribution."""
    venv = project / ".venv"
    python = venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    dist_info = (
        venv / "lib" / "python3.12" / "site-packages" / f"{dist}-7.0.0.dist-info"
    )
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Name: {dist}\n")


def test_justfile_wins_over_makefile(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"just", "make"})
    (tmp_path / "justfile").write_text("lint:\n    ruff check .\n")
    (tmp_path / "Makefile").write_text("lint:\n\truff check .\n")

    commands = detect_lint_commands(tmp_path)["all"]

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

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["make", "lint"]]


def test_uv_project_with_ruff_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["ruff"]\n')

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [
        ["uv", "run", "ruff", "check"],
        ["uv", "run", "ruff", "format", "--check"],
    ]


def test_uv_project_with_flake8_dependency(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["flake8"]\n')

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["uv", "run", "flake8"]]


def test_poe_task(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"poe"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poe.tasks]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["poe", "lint"]]


def test_pixi_task(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"pixi"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pixi.tasks]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["pixi", "run", "lint"]]


def test_hatch_env_script(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"hatch"})
    (tmp_path / "pyproject.toml").write_text(
        '[tool.hatch.envs.test.scripts]\nlint = "ruff check ."\n'
    )

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["hatch", "run", "test:lint"]]


def test_config_file_marker(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    (tmp_path / ".flake8").touch()

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [["flake8"]]
    assert commands[0]["source"] == "config-file"


def test_invalid_toml_skips_pyproject_sources(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "poe", "pixi", "hatch"})
    (tmp_path / "pyproject.toml").write_text("[tool.uv\n")

    assert detect_lint_commands(tmp_path) == {"all": [], "files": []}


def test_venv_fallback(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    _fake_venv(tmp_path, "flake8")

    commands = detect_lint_commands(tmp_path)["all"]

    expected_python = str(Path(tmp_path).resolve() / ".venv" / "bin" / "python")
    assert [c["argv"] for c in commands] == [[expected_python, "-m", "flake8"]]
    assert commands[0]["source"] == "venv"


def test_venv_found_through_symlinked_project_dir(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    _fake_venv(real, "flake8")

    commands = detect_lint_commands(link)["all"]

    expected_python = str(link.resolve() / ".venv" / "bin" / "python")
    assert [c["argv"] for c in commands] == [[expected_python, "-m", "flake8"]]
    assert commands[0]["source"] == "venv"


@pytest.mark.parametrize(
    ("tool", "argv"),
    [
        ("pylint", ["uv", "run", "pylint", "."]),
        ("black", ["uv", "run", "black", "--check", "."]),
        ("isort", ["uv", "run", "isort", "--check-only", "."]),
    ],
    ids=["pylint", "black", "isort"],
)
def test_project_target_declared_as_project_args(tmp_path, monkeypatch, tool, argv):
    _patch_which(monkeypatch, {"uv"})
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text(f'[dependency-groups]\ndev = ["{tool}"]\n')

    commands = detect_lint_commands(tmp_path)["all"]

    assert [c["argv"] for c in commands] == [argv]
    assert commands[0]["project_args"] == ["."]


def test_venv_command_declares_project_args(tmp_path, monkeypatch):
    _patch_which(monkeypatch, set())
    _fake_venv(tmp_path, "black")

    commands = detect_lint_commands(tmp_path)["all"]

    assert commands[0]["argv"][-2:] == ["--check", "."]
    assert commands[0]["project_args"] == ["."]


def test_no_lint_commands(tmp_path, monkeypatch):
    _patch_which(monkeypatch, {"uv", "just", "make", "poe", "pixi", "hatch"})

    assert detect_lint_commands(tmp_path) == {"all": [], "files": []}
