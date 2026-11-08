"""Auto-register a pytest marker per brick, so tests can run per brick via `pytest -m`.

Replaces the static `markers` list in pyproject.toml: brick directories under
components/ and bases/ are scanned here, so a new brick gets its marker
automatically, with no config edit.
"""

from pathlib import Path

import pytest

WORKSPACE = Path(__file__).parent.parent
BRICK_DIRS = ("components", "bases")


def brick_names() -> list[str]:
    """Leaf directory names of every brick in the workspace."""
    return sorted(
        d.name
        for brick_type in BRICK_DIRS
        for d in (WORKSPACE / brick_type).glob("*/*")
        if d.is_dir()
    )


def marker_line(name: str) -> str:
    return f"{name}: tests for the {name} brick"


def pytest_configure(config: pytest.Config) -> None:
    for name in brick_names():
        config.addinivalue_line("markers", marker_line(name))
