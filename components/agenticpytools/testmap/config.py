"""Pytest configuration lookup: ini options, testpaths, and test file patterns."""

import configparser
import tomllib
from pathlib import Path, PurePosixPath

_DEFAULT_PATTERNS = ("test_*.py", "*_test.py")


def pytest_ini(project: Path) -> dict:
    """The project's pytest ini options, from the first config file in pytest's order."""
    root = Path(project).expanduser().resolve()

    for options in (
        _ini_options(root / "pytest.ini", "pytest"),
        _toml_ini_options(root / "pyproject.toml"),
        _ini_options(root / "tox.ini", "pytest"),
        _ini_options(root / "setup.cfg", "tool:pytest"),
    ):
        if options is not None:
            return options

    return {}


def testpaths(project: Path) -> tuple[str, ...]:
    """The project's pytest testpaths roots, normalized; empty means the whole project."""
    root = Path(project).expanduser().resolve()
    options = pytest_ini(root)

    return tuple(
        normalized
        for path in _as_list(options.get("testpaths", []))
        if (normalized := _normalized_root(path, root)) is not None
    )


def python_files(project: Path) -> tuple[str, ...]:
    """The project's pytest python_files patterns, defaulting to pytest's."""
    patterns = _as_list(pytest_ini(project).get("python_files", []))

    return tuple(patterns) or _DEFAULT_PATTERNS


def _ini_options(path: Path, section: str) -> dict | None:
    """A config file's pytest options, or None when file or section is missing."""
    parser = configparser.ConfigParser()

    try:
        parser.read(path)
    except (OSError, configparser.Error):
        return None

    if not parser.has_section(section):
        return None

    return dict(parser[section])


def _toml_ini_options(path: Path) -> dict | None:
    """The pyproject [tool.pytest.ini_options] table, or None when missing."""
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    tool = data.get("tool", {})
    pytest = tool.get("pytest", {}) if isinstance(tool, dict) else {}
    options = pytest.get("ini_options") if isinstance(pytest, dict) else None

    return dict(options) if isinstance(options, dict) else None


def _as_list(value: object) -> list[str]:
    """A config value in string or list form, as a list of strings."""
    if isinstance(value, str):
        return value.split()

    if isinstance(value, list):
        return [str(item) for item in value]

    return []


def _normalized_root(path: str, root: Path) -> str | None:
    """A testpaths entry as a project-relative root; '' matches all, None when outside."""
    entry = path.removeprefix("./").rstrip("/")

    if PurePosixPath(entry).is_absolute():
        try:
            relative = Path(entry).resolve().relative_to(root).as_posix()
        except ValueError:
            return None

        return "" if relative == "." else relative

    return "" if entry in ("", ".") else entry
