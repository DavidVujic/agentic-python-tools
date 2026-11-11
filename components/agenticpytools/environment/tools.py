"""Project package-manager detection: uv, pixi, pdm, poetry, hatch."""

import shutil
import tomllib
from pathlib import Path

PROJECT_TOOLS = (
    ("uv", "uv.lock", "tool.uv", "uv", ["uv", "run"]),
    ("pixi", "pixi.lock", "tool.pixi", "pixi", ["pixi", "run"]),
    ("pdm", "pdm.lock", "tool.pdm", "pdm", ["pdm", "run"]),
    ("poetry", "poetry.lock", "tool.poetry", "poetry", ["poetry", "run"]),
    ("hatch", None, "tool.hatch", "hatch", ["hatch", "run"]),
)


def _dotted_keys(table: dict) -> set[str]:
    """Dotted keys of nested tables, e.g. 'tool.uv' for [tool.uv]."""
    keys = set(table)

    for key, value in table.items():
        if isinstance(value, dict):
            keys |= {f"{key}.{nested}" for nested in _dotted_keys(value)}

    return keys


def _pyproject_sections(project: Path) -> set[str]:
    """Dotted table keys in the project's pyproject.toml."""
    try:
        with (project / "pyproject.toml").open("rb") as file:
            data = tomllib.load(file)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return set()

    return _dotted_keys(data)


def _tool_source(
    project: Path, lock: str | None, section: str, sections: set[str]
) -> str | None:
    """The marker that makes a tool a candidate: its lockfile or pyproject section."""
    if lock is not None and (project / lock).exists():
        return lock

    return section if section in sections else None


def project_tool(project: Path) -> dict | None:
    """The project's package manager, from its lockfile or a pyproject section."""
    sections = _pyproject_sections(project)

    for name, lock, section, binary, prefix in PROJECT_TOOLS:
        source = _tool_source(project, lock, section, sections)

        if source is not None and shutil.which(binary) is not None:
            return {"tool": name, "prefix": list(prefix), "source": source}

    return None
