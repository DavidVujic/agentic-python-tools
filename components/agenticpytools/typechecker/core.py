"""Type check command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import TYPE_CHECKERS


def detect_typecheck_commands(project: Path) -> list[dict]:
    """Type check commands from the first source that finds any, in ladder order."""
    return detect_commands(project, TYPE_CHECKERS, ("typecheck", "type-check", "types"))
