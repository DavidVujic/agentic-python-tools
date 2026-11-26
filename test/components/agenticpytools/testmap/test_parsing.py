"""Unit tests for the dotted module names extracted from a file's imports."""

from pathlib import Path

import pytest
from agenticpytools.testmap import affected_tests, imports_of

pytestmark = pytest.mark.testmap


def _write(project: Path, rel_path: str, content: str) -> None:
    path = project / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _imports_of(project: Path, rel_path: str, content: str) -> frozenset[str]:
    _write(project, rel_path, content)

    return imports_of(project, rel_path)


def test_import_module_call_yields_module(tmp_path):
    content = "import importlib\n\nmod = importlib.import_module('pkg.mod')\n"

    assert _imports_of(tmp_path, "caller.py", content) == {"importlib", "pkg.mod"}


def test_import_module_relative_to_package_keyword(tmp_path):
    content = """import importlib

mod = importlib.import_module('.mod', package='pkg')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {"importlib", "pkg.mod"}


def test_import_module_relative_to_own_package(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    content = "import importlib\n\nmod = importlib.import_module('.mod')\n"

    assert _imports_of(tmp_path, "pkg/caller.py", content) == {"importlib", "pkg.mod"}


def test_import_module_relative_to_positional_package(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    content = "import importlib\n\nmod = importlib.import_module('.mod', 'other')\n"

    assert _imports_of(tmp_path, "pkg/caller.py", content) == {"importlib", "other.mod"}


def test_import_module_name_keyword_yields_module(tmp_path):
    content = "import importlib\n\nmod = importlib.import_module(name='pkg.kw')\n"

    assert _imports_of(tmp_path, "caller.py", content) == {"importlib", "pkg.kw"}


def test_import_builtin_call_yields_module(tmp_path):
    content = "mod = __import__('pkg.mod')\n"

    assert _imports_of(tmp_path, "caller.py", content) == {"pkg.mod"}


def test_import_string_call_yields_module_and_prefixes(tmp_path):
    content = """from django.utils import module_loading

thing = module_loading.import_string('pkg.mod.attr')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {
        "django.utils",
        "django.utils.module_loading",
        "pkg.mod.attr",
        "pkg.mod",
        "pkg",
    }


def test_get_model_two_args_yield_models_module(tmp_path):
    content = """from django.apps import apps

model = apps.get_model('app', 'Model')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {
        "django.apps",
        "django.apps.apps",
        "app.models",
        "app",
    }


def test_get_model_single_arg_yields_models_module(tmp_path):
    content = "model = apps.get_model('app.Model')\n"

    assert _imports_of(tmp_path, "caller.py", content) == {"app.models", "app"}


def test_get_model_keyword_args_yield_models_module(tmp_path):
    content = """from django.apps import apps

model = apps.get_model(app_label='app', model_name='Model')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {
        "django.apps",
        "django.apps.apps",
        "app.models",
        "app",
    }


def test_override_settings_yields_nested_strings_and_prefixes(tmp_path):
    content = """from django.test import override_settings

@override_settings(
    MIDDLEWARE=['pkg.mod.attr', ('pkg.tuple',)],
    BACKENDS={'k': 'pkg.dict'},
    FLAGS={'pkg.set'},
)
def test_thing():
    assert True
"""

    assert _imports_of(tmp_path, "caller.py", content) == {
        "django.test",
        "django.test.override_settings",
        "pkg.mod.attr",
        "pkg.mod",
        "pkg",
        "pkg.tuple",
        "pkg.dict",
        "pkg.set",
    }


def test_non_literal_dynamic_import_arguments_are_ignored(tmp_path):
    content = """import importlib

name = 'pkg.mod'
mod = importlib.import_module(name)
mod = importlib.import_module(f'pkg.{name}')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {"importlib"}


def test_empty_string_dynamic_imports_are_ignored(tmp_path):
    content = """import importlib

from django.apps import apps
from django.utils import module_loading

mod = __import__('')
mod = importlib.import_module('')
model = apps.get_model('')
thing = module_loading.import_string('')
"""

    assert _imports_of(tmp_path, "caller.py", content) == {
        "importlib",
        "django.apps",
        "django.apps.apps",
        "django.utils",
        "django.utils.module_loading",
    }


def _affected_tests(project: Path, module: str, content: str) -> list[str] | None:
    """Affected tests for a change to one module, given a test file using it."""
    package, _, file = module.partition("/")
    _write(project, f"{package}/__init__.py", "")
    _write(project, module, "x = 1\n")
    _write(project, f"test/test_{file.removesuffix('.py')}.py", content)

    return affected_tests(project, [module])


def test_changed_module_affects_test_using_import_string(tmp_path):
    content = """from django.utils.module_loading import import_string

thing = import_string('pkg.mod.attr')
"""

    assert _affected_tests(tmp_path, "pkg/mod.py", content) == ["test/test_mod.py"]


def test_changed_module_affects_test_using_import_module(tmp_path):
    content = """import importlib

mod = importlib.import_module('pkg.mod')
"""

    assert _affected_tests(tmp_path, "pkg/mod.py", content) == ["test/test_mod.py"]


def test_changed_module_affects_test_using_import_builtin(tmp_path):
    content = "mod = __import__('pkg.mod')\n"

    assert _affected_tests(tmp_path, "pkg/mod.py", content) == ["test/test_mod.py"]


def test_changed_module_affects_test_using_get_model(tmp_path):
    content = """from django.apps import apps

model = apps.get_model('app', 'Model')
"""

    assert _affected_tests(tmp_path, "app/models.py", content) == [
        "test/test_models.py"
    ]


def test_changed_module_affects_test_using_override_settings(tmp_path):
    content = """from django.test import override_settings

@override_settings(BACKEND='pkg.mod.attr')
def test_mod():
    assert True
"""

    assert _affected_tests(tmp_path, "pkg/mod.py", content) == ["test/test_mod.py"]


def test_changed_module_affects_test_using_relative_import_module(tmp_path):
    content = """import importlib

mod = importlib.import_module('.mod', package='pkg')
"""

    assert _affected_tests(tmp_path, "pkg/mod.py", content) == ["test/test_mod.py"]
