"""Unit tests for mapping changed files to affected test files."""

from pathlib import Path

import pytest
from agenticpytools.testmap import affected_tests, update

pytestmark = pytest.mark.testmap


def _write(project: Path, rel_path: str, content: str) -> None:
    path = project / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_changed_module_affects_importing_test(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg.module import x\n")

    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_module.py"]


def test_changed_test_file_affects_itself(tmp_path):
    _write(tmp_path, "test/test_module.py", "def test_module():\n    assert True\n")

    assert affected_tests(tmp_path, ["test/test_module.py"]) == ["test/test_module.py"]


def test_changed_module_affects_test_through_non_test_module(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "helper.py", "from pkg import module\n")
    _write(tmp_path, "test/test_helper.py", "import helper\n")

    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_helper.py"]


def test_changed_module_affects_test_from_package_import(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg import module\n")

    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_module.py"]


def test_changed_module_affects_test_through_relative_import(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/other.py", "x = 1\n")
    _write(tmp_path, "pkg/module.py", "from .other import x\n")
    _write(tmp_path, "test/test_module.py", "from pkg import module\n")

    assert affected_tests(tmp_path, ["pkg/other.py"]) == ["test/test_module.py"]


def test_changed_package_init_affects_submodule_tests(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg import module\n")

    assert affected_tests(tmp_path, ["pkg/__init__.py"]) == ["test/test_module.py"]


def test_changed_conftest_affects_tests_in_its_subtree(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/unit/conftest.py", "import pytest\n")
    _write(tmp_path, "test/unit/test_deep.py", "from pkg import module\n")
    _write(tmp_path, "test/test_shallow.py", "from pkg import module\n")

    affected = affected_tests(tmp_path, ["test/unit/conftest.py"])

    assert affected == ["test/unit/test_deep.py"]


def test_deleted_file_is_removed_from_graph(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "helper.py", "from pkg import module\n")
    _write(tmp_path, "test/test_helper.py", "import helper\n")
    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_helper.py"]

    (tmp_path / "helper.py").unlink()
    update(tmp_path, ["helper.py"])

    assert affected_tests(tmp_path, ["pkg/module.py"]) == []


def test_new_file_is_added_to_graph_when_changed(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg import module\n")
    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_module.py"]

    _write(tmp_path, "test/test_more.py", "from pkg import module\n")
    update(tmp_path, ["test/test_more.py"])

    assert affected_tests(tmp_path, ["pkg/module.py"]) == [
        "test/test_module.py",
        "test/test_more.py",
    ]


def test_deleted_change_is_unknown(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg import module\n")
    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_module.py"]

    (tmp_path / "pkg" / "module.py").unlink()

    assert affected_tests(tmp_path, ["pkg/module.py"]) is None


def test_missing_change_is_unknown(tmp_path):
    assert affected_tests(tmp_path, ["missing.py"]) is None


def test_pyproject_testpaths_scopes_test_discovery(tmp_path):
    config = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    _write(tmp_path, "pyproject.toml", config)
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "pkg/only_other.py", "y = 2\n")
    _write(tmp_path, "tests/test_a.py", "from pkg.module import x\n")
    _write(tmp_path, "other/test_b.py", "from pkg import only_other\n")

    assert affected_tests(tmp_path, ["tests/test_a.py"]) == ["tests/test_a.py"]
    assert affected_tests(tmp_path, ["other/test_b.py"]) == []
    assert affected_tests(tmp_path, ["pkg/only_other.py"]) == []
    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["tests/test_a.py"]


def test_pytest_ini_testpaths_scopes_test_discovery(tmp_path):
    _write(tmp_path, "pytest.ini", "[pytest]\ntestpaths = tests\n")
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "tests/test_a.py", "import pkg.module\n")
    _write(tmp_path, "other/test_b.py", "import pkg.module\n")

    assert affected_tests(tmp_path, ["tests/test_a.py"]) == ["tests/test_a.py"]
    assert affected_tests(tmp_path, ["other/test_b.py"]) == []
    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["tests/test_a.py"]


def test_absolute_testpath_scopes_test_discovery(tmp_path):
    tests = (tmp_path / "tests").resolve()
    testpaths = f'[tool.pytest.ini_options]\ntestpaths = ["{tests}"]\n'
    _write(tmp_path, "pyproject.toml", testpaths)
    _write(tmp_path, "tests/test_a.py", "")
    _write(tmp_path, "other/test_b.py", "")

    assert affected_tests(tmp_path, ["tests/test_a.py"]) == ["tests/test_a.py"]
    assert affected_tests(tmp_path, ["other/test_b.py"]) == []


def test_absolute_testpath_outside_project_selects_whole_project(tmp_path):
    outside = "/definitely/outside/the/project"
    testpaths = f'[tool.pytest.ini_options]\ntestpaths = ["{outside}"]\n'
    _write(tmp_path, "pyproject.toml", testpaths)
    _write(tmp_path, "test/test_any.py", "")

    assert affected_tests(tmp_path, ["test/test_any.py"]) == ["test/test_any.py"]


def test_python_files_config_overrides_test_patterns(tmp_path):
    config = '[tool.pytest.ini_options]\npython_files = ["*_spec.py"]\n'
    _write(tmp_path, "pyproject.toml", config)
    _write(tmp_path, "test/foo_spec.py", "")
    _write(tmp_path, "test/test_foo.py", "")

    assert affected_tests(tmp_path, ["test/foo_spec.py"]) == ["test/foo_spec.py"]
    assert affected_tests(tmp_path, ["test/test_foo.py"]) == []


def test_pytest_ini_takes_precedence_over_pyproject(tmp_path):
    pyproject = '[tool.pytest.ini_options]\ntestpaths = ["other"]\n'
    _write(tmp_path, "pytest.ini", "[pytest]\ntestpaths = tests\n")
    _write(tmp_path, "pyproject.toml", pyproject)
    _write(tmp_path, "tests/test_a.py", "")
    _write(tmp_path, "other/test_b.py", "")

    assert affected_tests(tmp_path, ["tests/test_a.py"]) == ["tests/test_a.py"]
    assert affected_tests(tmp_path, ["other/test_b.py"]) == []


def test_pyproject_without_pytest_section_keeps_defaults(tmp_path):
    _write(tmp_path, "pyproject.toml", "[tool.black]\nline-length = 80\n")
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/module.py", "x = 1\n")
    _write(tmp_path, "test/test_module.py", "from pkg.module import x\n")

    assert affected_tests(tmp_path, ["pkg/module.py"]) == ["test/test_module.py"]
