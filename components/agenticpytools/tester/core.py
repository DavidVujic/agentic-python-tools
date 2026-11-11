"""Test command detection for a project, from justfile down to the venv."""

from pathlib import Path

from agenticpytools.checks import detect_commands

from .tools import TEST_TOOLS


def detect_test_commands(project: Path) -> list[dict]:
    """Test commands from the first source that finds any, in ladder order."""
    return detect_commands(project, TEST_TOOLS, ("test", "tests"))
