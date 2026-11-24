"""Type check command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import TYPE_CHECKERS


def detect_typecheck_commands(project: Path) -> dict[str, list[dict]]:
    """Type check commands in two scopes: the all and the file-scoped ones."""
    return detect_commands(project, TYPE_CHECKERS, ("typecheck", "type-check", "types"))
