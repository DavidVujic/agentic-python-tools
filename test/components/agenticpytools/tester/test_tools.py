"""Unit tests for the tester tools table and dependency-name helpers."""

import pytest
from agenticpytools.tester.tools import normalize_dep_name

pytestmark = pytest.mark.tester


def test_normalize_dep_name():
    assert normalize_dep_name("PyTest>=8") == "pytest"
    assert normalize_dep_name("nox[all]") == "nox"
    assert normalize_dep_name("My_Test.Tool") == "my-test-tool"
