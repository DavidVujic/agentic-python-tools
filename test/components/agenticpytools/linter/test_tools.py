"""Unit tests for the linter tools table and dependency-name helpers."""

import pytest
from agenticpytools.linter.tools import normalize_dep_name

pytestmark = pytest.mark.linter


def test_normalize_dep_name():
    assert normalize_dep_name("Flake8>=7") == "flake8"
    assert normalize_dep_name("ruff[all]") == "ruff"
    assert normalize_dep_name("My_Lint.Tool") == "my-lint-tool"
