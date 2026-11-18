"""Map changed source files to the test files they affect."""

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from agenticpytools.testmap.config import _DEFAULT_PATTERNS
from agenticpytools.testmap.graph import _LOCK, _loaded, _sync
from agenticpytools.testmap.parsing import INIT_PY


def is_test_file(rel_path: str, patterns: tuple[str, ...] = _DEFAULT_PATTERNS) -> bool:
    """True for a path whose basename matches the given test file patterns."""
    name = PurePosixPath(rel_path).name

    return any(fnmatch(name, pattern) for pattern in patterns)


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

    if name == INIT_PY:
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
