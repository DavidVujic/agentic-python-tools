"""The cached per-project import graph and its incremental updates."""

import os
import threading
from pathlib import Path, PurePosixPath

from agenticpytools.testmap.config import python_files, testpaths
from agenticpytools.testmap.parsing import imports_of, module_of
from agenticpytools.watcher.core import IGNORED_DIR_NAMES

_GRAPHS: dict[str, dict] = {}
_LOCK = threading.Lock()


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
