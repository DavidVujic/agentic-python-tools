"""Debounced batches of changed Python files in a project."""

import importlib.util
import os
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

IGNORED_DIR_NAMES = {
    ".venv",
    ".git",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    "node_modules",
    "dist",
    "build",
    ".eggs",
}


def changed_python_files(project: Path, debounce: float = 0.5) -> Iterator[list[str]]:
    """Yield debounced batches of changed .py paths relative to the project."""
    path = Path(project).expanduser().resolve()

    if importlib.util.find_spec("watchfiles") is None:
        return _poll(path, interval=max(debounce, 0.2))

    return _watchfiles_events(path, debounce)


def _ignored_dir(name: str) -> bool:
    """True for directory names that are never watched."""
    return name in IGNORED_DIR_NAMES or name.endswith(".egg-info")


def _is_ignored(path: Path, project: Path) -> bool:
    """True when any part of the path below the project is an ignored directory."""
    try:
        parts = path.relative_to(project).parts
    except ValueError:
        return False

    return any(_ignored_dir(part) for part in parts)


def _relative(path: Path, project: Path) -> str | None:
    """Relative posix path for a watched .py file, else None."""
    if path.name.endswith(".py") and not _is_ignored(path, project):
        return path.relative_to(project).as_posix()

    return None


def _watched_files(project: Path) -> dict[str, float]:
    """Snapshot of watched .py files keyed by relative posix path."""
    snapshot: dict[str, float] = {}

    for root, dirnames, filenames in os.walk(project):
        dirnames[:] = [name for name in dirnames if not _ignored_dir(name)]

        for name in filenames:
            if not name.endswith(".py"):
                continue

            path = Path(root) / name
            try:
                mtime = path.stat().st_mtime
            except FileNotFoundError:
                continue

            snapshot[path.relative_to(project).as_posix()] = mtime

    return snapshot


def _changed(before: dict[str, float], after: dict[str, float]) -> list[str]:
    """Sorted paths that are new, modified, or deleted between snapshots."""
    changed = {path for path, mtime in after.items() if before.get(path) != mtime}
    deleted = set(before) - set(after)

    return sorted(changed | deleted)


def _poll(project: Path, interval: float) -> Iterator[list[str]]:
    """Poll snapshots forever, yielding each non-empty batch of changed paths."""
    previous = _watched_files(project)

    while True:
        time.sleep(interval)
        current = _watched_files(project)
        changed = _changed(previous, current)

        if changed:
            yield changed

        previous = current


def _watched_paths(
    events: Iterable[Iterable[tuple[int, str]]], project: Path
) -> Iterator[set[str]]:
    """Each watchfiles event batch as a set of relative watched .py paths."""
    for changes in events:
        yield {
            relative
            for _, changed in changes
            if (relative := _relative(Path(changed), project)) is not None
        }


def _watchfiles_events(project: Path, debounce: float) -> Iterator[list[str]]:
    """Yield sorted batches of changed .py paths after events stay quiet."""
    from watchfiles import watch

    events = watch(
        str(project),
        watch_filter=None,
        debounce=50,
        step=50,
        rust_timeout=100,
        yield_on_timeout=True,
    )
    batch: set[str] = set()
    deadline = 0.0

    for paths in _watched_paths(events, project):
        now = time.monotonic()

        if batch and now >= deadline:
            yield sorted(batch)
            batch = set()

        batch |= paths
        deadline = now + debounce if paths else deadline
