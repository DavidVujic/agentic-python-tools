"""Lint command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.environment import project_tool
from agenticpytools.linter.sources import (
    justfile_commands,
    makefile_commands,
    pyproject_linter_commands,
    pyproject_task_commands,
    venv_commands,
)


def detect_lint_commands(project: Path) -> list[dict]:
    """Lint commands from the first source that finds any, in ladder order."""
    path = Path(project).expanduser().resolve()
    prefix = (project_tool(path) or {}).get("prefix", [])

    for source in (
        justfile_commands,
        makefile_commands,
        pyproject_task_commands,
        lambda p: pyproject_linter_commands(p, prefix),
        venv_commands,
    ):
        commands = source(path)

        if commands:
            return [{**cmd, "cwd": str(path)} for cmd in commands]

    return []
