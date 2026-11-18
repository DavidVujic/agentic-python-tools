"""Static per-file Python analysis: module names, packages, and imports."""

import ast
from collections.abc import Iterator
from pathlib import Path

INIT_PY = "__init__.py"


def module_of(project: Path, rel_path: str) -> str | None:
    """Dotted module name of a relative path, or None when outside the project."""
    root = Path(project).expanduser().resolve()
    file = (root / rel_path).resolve()

    try:
        rel = file.relative_to(root)
    except ValueError:
        return None

    *_, name = rel.parts

    if name == INIT_PY:
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
    if (directory / INIT_PY).is_file():
        return True

    children = list(directory.iterdir())

    return not any(child.is_file() for child in children) and any(
        (child / INIT_PY).is_file() for child in children if child.is_dir()
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
