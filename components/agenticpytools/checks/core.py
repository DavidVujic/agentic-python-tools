"""Command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks.sources import (
    justfile_commands,
    makefile_commands,
    pyproject_task_commands,
    pyproject_tool_commands,
    venv_commands,
)
from agenticpytools.checks.tools import Tool
from agenticpytools.environment import project_tool


def detect_commands(
    project: Path, tools: dict[str, Tool], recipe_names: tuple[str, ...]
) -> dict[str, list[dict]]:
    """The all commands from the first source, and file-scoped ones from it or deeper."""
    path = Path(project).expanduser().resolve()
    prefix = (project_tool(path) or {}).get("prefix", [])
    sources = (
        lambda p: justfile_commands(p, recipe_names),
        lambda p: makefile_commands(p, recipe_names),
        lambda p: pyproject_task_commands(p, recipe_names),
        lambda p: pyproject_tool_commands(p, prefix, tools),
        lambda p: venv_commands(p, tools),
    )
    all_commands: list[dict] = []
    file_commands: list[dict] = []

    for source in sources:
        commands = source(path)

        if not commands:
            continue

        if not all_commands:
            all_commands = _decorated(commands, path)

        file_commands = _decorated(_file_scoped(commands), path)

        if file_commands:
            break

    return {"all": all_commands, "files": file_commands or _file_scoped(all_commands)}


def _decorated(commands: list[dict], path: Path) -> list[dict]:
    """The commands with the project's cwd attached."""
    return [{**cmd, "cwd": str(path)} for cmd in commands]


def _file_scoped(commands: list[dict]) -> list[dict]:
    """The commands of tools that accept a file list."""
    return [cmd for cmd in commands if cmd.get("takes_files")]
