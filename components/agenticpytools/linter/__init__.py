"""Lint command detection for a project: justfile, Makefile, pyproject, or venv."""

from agenticpytools.linter.core import detect_lint_commands

__all__ = ["detect_lint_commands"]
