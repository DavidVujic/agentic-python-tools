"""Generic command sources: justfile, Makefile, pyproject tasks, pyproject tools, and venv."""

import configparser
import importlib.metadata
import re
import shutil
import tomllib
from pathlib import Path

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name
from agenticpytools.environment import project_tool, venv_dir, venv_python

JUSTFILES = ("justfile", "Justfile", ".justfile")
MAKEFILES = ("Makefile", "GNUmakefile")
INI_FILES = ("setup.cfg", "tox.ini")


def _command(argv: list[str], source: str, tool: str) -> dict:
    """A detected command; detect_commands adds the cwd."""
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


def _recipe_name(path: Path | None, pattern: str) -> str | None:
    """The first recipe name matching the pattern, or None."""
    if path is None:
        return None

    return next(
        (
            match.group(1)
            for line in path.read_text().splitlines()
            if (match := re.search(pattern, line)) is not None
        ),
        None,
    )


def _task_name(table: dict, names: tuple[str, ...]) -> str | None:
    """The first task name present in the table."""
    return next((name for name in names if name in table), None)


def justfile_commands(project: Path, recipe_names: tuple[str, ...]) -> list[dict]:
    """Command from a justfile recipe matching the recipe names."""
    if shutil.which("just") is None:
        return []

    pattern = "^(" + "|".join(map(re.escape, recipe_names)) + r")\b[^:]*:"
    recipe = _recipe_name(_first_file(project, JUSTFILES), pattern)

    if recipe is None:
        return []

    return [_command(["just", recipe], "justfile", "just")]


def makefile_commands(project: Path, recipe_names: tuple[str, ...]) -> list[dict]:
    """Command from a Makefile target matching the recipe names."""
    if shutil.which("make") is None:
        return []

    pattern = "^(" + "|".join(map(re.escape, recipe_names)) + "):"
    target = _recipe_name(_first_file(project, MAKEFILES), pattern)

    if target is None:
        return []

    return [_command(["make", target], "makefile", "make")]


def pyproject_task_commands(project: Path, recipe_names: tuple[str, ...]) -> list[dict]:
    """Commands from pyproject task runners: poe, pixi, and hatch."""
    data = _read_pyproject(project)

    if data is None:
        return []

    tables = data.get("tool", {})
    manager = project_tool(project)

    return [
        *_poe_commands(tables.get("poe", {}), manager, recipe_names),
        *_pixi_commands(tables.get("pixi", {}), manager, recipe_names),
        *_hatch_commands(tables.get("hatch", {}), recipe_names),
    ]


def _poe_commands(
    poe: dict, manager: dict | None, recipe_names: tuple[str, ...]
) -> list[dict]:
    """Command from a poe task, via the project manager or a global poe."""
    task = _task_name(poe.get("tasks", {}), recipe_names)

    if task is None:
        return []

    if manager is None and shutil.which("poe") is None:
        return []

    prefix = manager["prefix"] if manager is not None else []
    return [_command(prefix + ["poe", task], "pyproject-task", "poe")]


def _pixi_commands(
    pixi: dict, manager: dict | None, recipe_names: tuple[str, ...]
) -> list[dict]:
    """Command from a pixi task."""
    task = _task_name(pixi.get("tasks", {}), recipe_names)

    if task is None:
        return []

    if not _pixi_available(manager):
        return []

    return [_command(["pixi", "run", task], "pyproject-task", "pixi")]


def _pixi_available(manager: dict | None) -> bool:
    """Whether pixi is installed or is the project's tool manager."""
    return shutil.which("pixi") is not None or (manager or {}).get("tool") == "pixi"


def _hatch_commands(hatch: dict, recipe_names: tuple[str, ...]) -> list[dict]:
    """Commands from hatch environment scripts."""
    if shutil.which("hatch") is None:
        return []

    commands = []

    for name, env in hatch.get("envs", {}).items():
        task = _task_name(env.get("scripts", {}), recipe_names)

        if task is not None:
            script = task if name == "default" else f"{name}:{task}"
            commands.append(
                _command(["hatch", "run", script], "pyproject-task", "hatch")
            )

    return commands


def pyproject_tool_commands(
    project: Path, prefix: list[str], tools: dict[str, Tool]
) -> list[dict]:
    """Commands for tools declared as dependencies or via config markers."""
    data = _read_pyproject(project)

    return [
        _command(prefix + [name] + args, source, name)
        for name, source in _detected_tools(project, data, tools)
        for args in tools[name]["argvs"]
    ]


def _detected_tools(
    project: Path, data: dict | None, tools: dict[str, Tool]
) -> list[tuple[str, str]]:
    """Detected tools as (name, source) pairs in table order."""
    sections = _dotted_keys(data or {})
    ini = _ini_section_names(project)
    dep_tools = {name for name in dependency_names(data or {}) if name in tools}
    configured = {
        name
        for name, tool in tools.items()
        if _is_configured(project, tool, sections, ini)
    }

    return [
        (name, "pyproject" if name in dep_tools else "config-file")
        for name in tools
        if name in dep_tools or name in configured
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
    project: Path, tool: Tool, sections: set[str], ini: set[str]
) -> bool:
    """Whether any of the tool's config markers exists in the project."""
    return (
        _has_pyproject_section(tool, sections)
        or _has_section_prefix(tool, sections)
        or _has_ini_section(tool, ini)
        or _has_marker_file(project, tool)
    )


def _has_pyproject_section(tool: Tool, sections: set[str]) -> bool:
    """Whether a tool section exists in the pyproject tables."""
    return any(section in sections for section in tool.get("sections", []))


def _has_section_prefix(tool: Tool, sections: set[str]) -> bool:
    """Whether a pyproject section key matches a tool section prefix."""
    return any(
        _key_matches_prefix(key, prefix)
        for prefix in tool.get("section_prefixes", [])
        for key in sections
    )


def _key_matches_prefix(key: str, prefix: str) -> bool:
    """Whether the section key is the prefix or nested under it."""
    return key == prefix or key.startswith(f"{prefix}.")


def _has_ini_section(tool: Tool, ini: set[str]) -> bool:
    """Whether a tool section exists in setup.cfg or tox.ini."""
    return any(section in ini for section in tool.get("ini_sections", []))


def _has_marker_file(project: Path, tool: Tool) -> bool:
    """Whether one of the tool's marker files exists."""
    return any((project / filename).is_file() for filename in tool.get("files", []))


def venv_commands(project: Path, tools: dict[str, Tool]) -> list[dict]:
    """Commands using the tools installed in the project venv."""
    venv = venv_dir(project)

    if not venv.is_dir():
        return []

    try:
        python = str(venv_python(project))
    except FileNotFoundError:
        return []

    installed = _venv_packages(venv)

    return [
        _command([python, "-m", tools[name].get("module", name)] + args, "venv", name)
        for name in tools
        if name in installed
        for args in tools[name]["argvs"]
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
