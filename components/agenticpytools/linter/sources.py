"""Lint command sources: justfile, Makefile, pyproject tasks, linters, and venv."""

import configparser
import importlib.metadata
import re
import shutil
import tomllib
from pathlib import Path

from agenticpytools.environment import project_tool, venv_dir, venv_python
from agenticpytools.linter.tools import (
    LINTERS,
    Linter,
    dependency_names,
    normalize_dep_name,
)

JUSTFILES = ("justfile", "Justfile", ".justfile")
MAKEFILES = ("Makefile", "GNUmakefile")
INI_FILES = ("setup.cfg", "tox.ini")


def _command(argv: list[str], source: str, tool: str) -> dict:
    """A lint command; detect_lint_commands adds the cwd."""
    return {"argv": argv, "source": source, "tool": tool}


def _read_pyproject(project: Path) -> dict | None:
    """Parsed pyproject.toml, or None when missing or invalid."""
    try:
        with (project / "pyproject.toml").open("rb") as file:
            return tomllib.load(file)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return None


def _dotted_keys(table: dict) -> set[str]:
    """Dotted keys of nested tables, e.g. 'tool.ruff' for [tool.ruff]."""
    keys = set(table)

    for key, value in table.items():
        if isinstance(value, dict):
            keys |= {f"{key}.{nested}" for nested in _dotted_keys(value)}

    return keys


def _first_file(project: Path, names: tuple[str, ...]) -> Path | None:
    """The first existing file among the given names."""
    return next((project / name for name in names if (project / name).is_file()), None)


def _has_recipe(path: Path, pattern: str) -> bool:
    """Whether any line matches the recipe pattern."""
    return any(re.search(pattern, line) for line in path.read_text().splitlines())


def justfile_commands(project: Path) -> list[dict]:
    """Lint command from a justfile lint recipe."""
    if shutil.which("just") is None:
        return []

    justfile = _first_file(project, JUSTFILES)

    if justfile is None or not _has_recipe(justfile, r"^lint\b[^:]*:"):
        return []

    return [_command(["just", "lint"], "justfile", "just")]


def makefile_commands(project: Path) -> list[dict]:
    """Lint command from a Makefile lint target."""
    if shutil.which("make") is None:
        return []

    makefile = _first_file(project, MAKEFILES)

    if makefile is None or not _has_recipe(makefile, r"^lint:"):
        return []

    return [_command(["make", "lint"], "makefile", "make")]


def pyproject_task_commands(project: Path) -> list[dict]:
    """Lint commands from pyproject task runners: poe, pixi, and hatch."""
    data = _read_pyproject(project)

    if data is None:
        return []

    tables = data.get("tool", {})
    manager = project_tool(project)

    return [
        *_poe_commands(tables.get("poe", {}), manager),
        *_pixi_commands(tables.get("pixi", {}), manager),
        *_hatch_commands(tables.get("hatch", {})),
    ]


def _poe_commands(poe: dict, manager: dict | None) -> list[dict]:
    """Lint command from a poe task, via the project manager or a global poe."""
    if "lint" not in poe.get("tasks", {}):
        return []

    if manager is None and shutil.which("poe") is None:
        return []

    prefix = manager["prefix"] if manager is not None else []
    return [_command(prefix + ["poe", "lint"], "pyproject-task", "poe")]


def _pixi_commands(pixi: dict, manager: dict | None) -> list[dict]:
    """Lint command from a pixi task."""
    if "lint" not in pixi.get("tasks", {}):
        return []

    if shutil.which("pixi") is None and (manager or {}).get("tool") != "pixi":
        return []

    return [_command(["pixi", "run", "lint"], "pyproject-task", "pixi")]


def _hatch_commands(hatch: dict) -> list[dict]:
    """Lint commands from hatch environment scripts."""
    if shutil.which("hatch") is None:
        return []

    commands = []

    for name, env in hatch.get("envs", {}).items():
        if "lint" in env.get("scripts", {}):
            task = "lint" if name == "default" else f"{name}:lint"
            commands.append(_command(["hatch", "run", task], "pyproject-task", "hatch"))

    return commands


def pyproject_linter_commands(project: Path, prefix: list[str]) -> list[dict]:
    """Lint commands for linters declared as dependencies or via config markers."""
    data = _read_pyproject(project)
    sections = _dotted_keys(data or {})
    ini = _ini_section_names(project)

    dep_tools = {name for name in dependency_names(data or {}) if name in LINTERS}
    configured = {
        name
        for name, linter in LINTERS.items()
        if _is_configured(project, linter, sections, ini)
    }

    tools = [
        (name, "pyproject" if name in dep_tools else "config-file")
        for name in LINTERS
        if name in dep_tools or name in configured
    ]

    return [
        _command(prefix + [name] + args, source, name)
        for name, source in tools
        for args in LINTERS[name]["argvs"]
    ]


def _ini_section_names(project: Path) -> set[str]:
    """Section names present in setup.cfg or tox.ini."""
    names = set()

    for filename in INI_FILES:
        parser = configparser.ConfigParser()

        try:
            parser.read(project / filename)
        except configparser.Error:
            continue

        names |= set(parser.sections())

    return names


def _is_configured(
    project: Path, linter: Linter, sections: set[str], ini: set[str]
) -> bool:
    """Whether any of the linter's config markers exists in the project."""
    return (
        any(section in sections for section in linter.get("sections", []))
        or any(
            key == prefix or key.startswith(f"{prefix}.")
            for prefix in linter.get("section_prefixes", [])
            for key in sections
        )
        or any(section in ini for section in linter.get("ini_sections", []))
        or any((project / filename).is_file() for filename in linter.get("files", []))
    )


def venv_commands(project: Path) -> list[dict]:
    """Lint commands using the linters installed in the project venv."""
    venv = venv_dir(project)

    if not venv.is_dir():
        return []

    try:
        python = str(venv_python(project))
    except FileNotFoundError:
        return []

    installed = _venv_packages(venv)

    return [
        _command([python, "-m", LINTERS[name].get("module", name)] + args, "venv", name)
        for name in LINTERS
        if name in installed
        for args in LINTERS[name]["argvs"]
    ]


def _venv_packages(venv: Path) -> set[str]:
    """Normalized distribution names in the venv's site-packages."""
    lib = next((d for d in venv.iterdir() if d.name.lower() == "lib"), None)

    if lib is None:
        return set()

    site_packages = [*lib.glob("*/site-packages"), lib / "site-packages"]

    return {
        normalize_dep_name(dist.metadata["Name"] or "")
        for sp in site_packages
        if sp.is_dir()
        for dist in importlib.metadata.distributions(path=[str(sp)])
    }
