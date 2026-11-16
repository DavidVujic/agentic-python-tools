"""Debounced batches of changed Python files in a project."""

import threading
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


def changed_python_files(
    project: Path, debounce: float = 0.5, stop_event: threading.Event | None = None
) -> Iterator[list[str]]:
    """Yield debounced batches of changed .py paths until stop_event is set."""
    path = Path(project).expanduser().resolve()

    return _watchfiles_events(path, debounce, stop_event)


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


def _watchfiles_events(
    project: Path, debounce: float, stop_event: threading.Event | None = None
) -> Iterator[list[str]]:
    """Yield sorted batches of changed .py paths after events stay quiet."""
    from watchfiles import watch

    events = watch(
        str(project),
        watch_filter=None,
        debounce=50,
        step=50,
        rust_timeout=100,
        yield_on_timeout=True,
        stop_event=stop_event,
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
