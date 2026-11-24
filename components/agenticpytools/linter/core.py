"""Lint command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import LINTERS


def detect_lint_commands(project: Path) -> dict[str, list[dict]]:
    """Lint commands in two scopes: the all and the file-scoped ones."""
    return detect_commands(project, LINTERS, ("lint",))
