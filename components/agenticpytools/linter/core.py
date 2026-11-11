"""Lint command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import LINTERS


def detect_lint_commands(project: Path) -> list[dict]:
    """Lint commands from the first source that finds any, in ladder order."""
    return detect_commands(project, LINTERS, ("lint",))
