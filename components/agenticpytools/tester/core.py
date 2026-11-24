"""Test command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import TEST_TOOLS


def detect_test_commands(project: Path) -> dict[str, list[dict]]:
    """Test commands in two scopes: the all and the file-scoped ones."""
    return detect_commands(project, TEST_TOOLS, ("test", "tests"))
