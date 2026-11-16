"""Unit tests for the tool-table dependency-name helpers."""

import pytest
from agenticpytools.checks.tools import normalize_dep_name

pytestmark = pytest.mark.checks


@pytest.mark.parametrize(
    ("dep", "expected"),
    [
        ("Flake8>=7", "flake8"),
        ("ruff[all]", "ruff"),
        ("My_Lint.Tool", "my-lint-tool"),
        ("PyTest>=8", "pytest"),
    ],
)
def test_normalize_dep_name(dep, expected):
    assert normalize_dep_name(dep) == expected
