"""Map changed source files to the test files they affect."""

import ast
import configparser
import os
import threading
import tomllib
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from agenticpytools.watcher.core import IGNORED_DIR_NAMES

_GRAPHS: dict[str, dict] = {}
_LOCK = threading.Lock()
_DEFAULT_PATTERNS = ("test_*.py", "*_test.py")


def is_test_file(rel_path: str, patterns: tuple[str, ...] = _DEFAULT_PATTERNS) -> bool:
    """True for a path whose basename matches the given test file patterns."""
    name = PurePosixPath(rel_path).name

    return any(fnmatch(name, pattern) for pattern in patterns)


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


def module_of(project: Path, rel_path: str) -> str | None:
    """Dotted module name of a relative path, or None when outside the project."""
    root = Path(project).expanduser().resolve()
    file = (root / rel_path).resolve()

    try:
        rel = file.relative_to(root)
    except ValueError:
        return None

    *_, name = rel.parts

    if name == "__init__.py":
        return ".".join(_package_of(file.parent, root)) or None

    return ".".join([*_package_of(file.parent, root), name.removesuffix(".py")])


def _package_of(directory: Path, root: Path) -> list[str]:
    """Package parts of a directory, up while each level is a package."""
    parts: list[str] = []
    current = directory

    while current != root and _is_package(current):
        parts.insert(0, current.name)
        current = current.parent

    return parts


def _is_package(directory: Path) -> bool:
    """True for a package, also counting namespace dirs that hold only package dirs."""
    if (directory / "__init__.py").is_file():
        return True

    children = list(directory.iterdir())

    return not any(child.is_file() for child in children) and any(
        (child / "__init__.py").is_file() for child in children if child.is_dir()
    )


def imports_of(project: Path, rel_path: str) -> frozenset[str]:
    """Dotted modules a file imports; unparsable or unreadable files import nothing."""
    root = Path(project).expanduser().resolve()
    file = (root / rel_path).resolve()

    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return frozenset()

    return frozenset(
        module
        for node in ast.walk(tree)
        for module in _imported_names(node, _package_of(file.parent, root))
    )


def _imported_names(node: ast.AST, package: list[str]) -> Iterator[str]:
    """The dotted modules one AST import node refers to."""
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        base = _from_base(node, package)

        if base is not None:
            yield base
            yield from (f"{base}.{alias.name}" for alias in node.names)


def _from_base(node: ast.ImportFrom, package: list[str]) -> str | None:
    """Absolute dotted module that a from-import refers to."""
    if not node.level:
        return node.module

    keep = len(package) - (node.level - 1)

    if keep < 0:
        return None

    parts = package[:keep]

    if node.module:
        parts.append(node.module)

    return ".".join(parts) or None


def _py_files(root: Path) -> list[str]:
    """All .py files under the project, outside ignored directories."""
    files: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in IGNORED_DIR_NAMES and not name.endswith(".egg-info")
        )
        files.extend(
            Path(dirpath, name).relative_to(root).as_posix()
            for name in filenames
            if name.endswith(".py")
        )

    return files


def _watched(rel_path: str) -> bool:
    """True for a relative path outside ignored directories."""
    return not any(
        part in IGNORED_DIR_NAMES or part.endswith(".egg-info")
        for part in PurePosixPath(rel_path).parts
    )


def _loaded(root: Path) -> dict:
    """The project's cached import graph, built on first use; call under _LOCK."""
    graph = _GRAPHS.get(str(root))

    if graph is None:
        graph = _empty_graph()
        graph["roots"] = testpaths(root)
        graph["patterns"] = python_files(root)
        _GRAPHS[str(root)] = graph

        for rel_path in _py_files(root):
            _add(graph, root, rel_path)

    return graph


def _empty_graph() -> dict:
    """A fresh graph: modules, imports, mtimes, importer edges, and test discovery config."""
    return {
        "modules": {},
        "imports": {},
        "mtimes": {},
        "importers": {},
        "roots": (),
        "patterns": (),
    }


def _add(graph: dict, root: Path, rel_path: str) -> None:
    """One file's module, imports, mtime, and importer edges into the graph."""
    imports = imports_of(root, rel_path)

    graph["modules"][rel_path] = module_of(root, rel_path)
    graph["imports"][rel_path] = imports
    graph["mtimes"][rel_path] = (root / rel_path).stat().st_mtime

    for module in imports:
        graph["importers"].setdefault(module, set()).add(rel_path)


def _remove(graph: dict, rel_path: str) -> None:
    """One file and its importer edges out of the graph."""
    for module in graph["imports"].pop(rel_path, frozenset()):
        graph["importers"].get(module, set()).discard(rel_path)

    graph["modules"].pop(rel_path, None)
    graph["mtimes"].pop(rel_path, None)


def update(project: Path, changed: list[str]) -> None:
    """Refresh the project's cached graph for a change batch."""
    root = Path(project).expanduser().resolve()

    with _LOCK:
        _sync(_loaded(root), root, changed)


def _sync(graph: dict, root: Path, changed: list[str]) -> None:
    """Apply one change batch to the graph; call under _LOCK."""
    for rel_path in changed:
        if not _watched(rel_path):
            continue

        file = root / rel_path

        if not file.is_file():
            _remove(graph, rel_path)
        elif file.stat().st_mtime != graph["mtimes"].get(rel_path):
            _remove(graph, rel_path)
            _add(graph, root, rel_path)


def affected_tests(project: Path, changed: list[str]) -> list[str] | None:
    """Affected test paths for a change batch, or None when all tests should run."""
    root = Path(project).expanduser().resolve()

    with _LOCK:
        graph = _loaded(root)
        _sync(graph, root, changed)
        affected = _affected(graph, root, changed)

        return None if affected is None else sorted(affected)


def _affected(graph: dict, root: Path, changed: list[str]) -> set[str] | None:
    """Test files reached by the changes, or None when a change is unmappable."""
    affected: set[str] = set()
    seeds: set[str] = set()

    for rel_path in changed:
        module = graph["modules"].get(rel_path)

        if module is None or not (root / rel_path).is_file():
            return None

        affected.update(_directly_affected(graph, rel_path))
        seeds.update(_seeds_for(graph, rel_path, module))

    return affected | _importing_tests(graph, seeds)


def _is_test(graph: dict, rel_path: str) -> bool:
    """True for a path this graph counts as a test file."""
    if not is_test_file(rel_path, graph["patterns"]):
        return False

    path = PurePosixPath(rel_path)
    roots = graph["roots"]

    return not roots or any(root == "" or path.is_relative_to(root) for root in roots)


def _directly_affected(graph: dict, rel_path: str) -> set[str]:
    """Test files a changed path affects by itself, without following imports."""
    name = PurePosixPath(rel_path).name

    if _is_test(graph, rel_path):
        return {rel_path}

    if name == "conftest.py":
        return _subtree_tests(graph, rel_path)

    return set()


def _seeds_for(graph: dict, rel_path: str, module: str) -> set[str]:
    """Graph modules to walk from for a changed file."""
    name = PurePosixPath(rel_path).name

    if name == "__init__.py":
        return {module, *_package_modules(graph, module)}

    return {module}


def _package_modules(graph: dict, package: str) -> set[str]:
    """Every known module inside the package."""
    return {
        module
        for module in graph["modules"].values()
        if module is not None and _within(module, package)
    }


def _within(module: str, package: str) -> bool:
    """True for a module inside the package."""
    return module.startswith(f"{package}.")


def _importing_tests(graph: dict, seeds: set[str]) -> set[str]:
    """Test files importing the seeded modules, also across non-test modules."""
    tests: set[str] = set()
    seen: set[str] = set()
    modules = set(seeds)

    while modules:
        module = modules.pop()

        if module in seen:
            continue

        seen.add(module)

        for importer in _importers_of(graph, module):
            _follow_importer(graph, importer, tests, modules)

    return tests


def _importers_of(graph: dict, module: str) -> set[str]:
    """Files importing a module, across every matching importer key."""
    keys = _matching_modules(module, graph["importers"])

    return {importer for key in keys for importer in graph["importers"][key]}


def _follow_importer(
    graph: dict, importer: str, tests: set[str], pending: set[str]
) -> None:
    """One importer of a changed module: an affected test, or a module to follow."""
    if _is_test(graph, importer):
        tests.add(importer)
    elif PurePosixPath(importer).name == "conftest.py":
        tests.update(_subtree_tests(graph, importer))
    else:
        module = graph["modules"].get(importer)

        if module is not None:
            pending.add(module)


def _matching_modules(seed: str, importers: dict[str, set[str]]) -> set[str]:
    """Importer keys for a seed; layout prefixes of either side still match."""
    return {
        key
        for key in importers
        if key == seed or key.endswith(f".{seed}") or seed.endswith(f".{key}")
    }


def _subtree_tests(graph: dict, conftest: str) -> set[str]:
    """Known test files in the conftest file's directory subtree."""
    directory = PurePosixPath(conftest).parent

    return {
        rel_path
        for rel_path in graph["imports"]
        if _is_test(graph, rel_path)
        and PurePosixPath(rel_path).is_relative_to(directory)
    }
