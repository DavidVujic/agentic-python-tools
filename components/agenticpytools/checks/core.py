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
) -> list[dict]:
    """Commands from the first source that finds any, in ladder order."""
    path = Path(project).expanduser().resolve()
    prefix = (project_tool(path) or {}).get("prefix", [])

    for source in (
        lambda p: justfile_commands(p, recipe_names),
        lambda p: makefile_commands(p, recipe_names),
        lambda p: pyproject_task_commands(p, recipe_names),
        lambda p: pyproject_tool_commands(p, prefix, tools),
        lambda p: venv_commands(p, tools),
    ):
        commands = source(path)

        if commands:
            return [{**cmd, "cwd": str(path)} for cmd in commands]

    return []
