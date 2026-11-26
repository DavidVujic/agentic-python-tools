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

    package = _package_of(file.parent, root)

    return frozenset(
        module for node in ast.walk(tree) for module in _imported_names(node, package)
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
    elif isinstance(node, ast.Call):
        yield from _dynamic_imports(node, package)


def _dynamic_imports(call: ast.Call, package: list[str]) -> Iterator[str]:
    """Dotted modules a string-based dynamic import call refers to."""
    name = _callee_name(call.func)

    if name == "__import__":
        yield from _import_builtin_names(call)
    elif name == "import_module":
        yield from _import_module_names(call, package)
    elif name == "import_string":
        yield from _import_string_names(call)
    elif name == "get_model":
        yield from _get_model_names(call)
    elif name == "override_settings":
        yield from _override_settings_names(call)


def _import_builtin_names(call: ast.Call) -> Iterator[str]:
    """The module an __import__ call names."""
    module = _first_str_arg(call)

    if module:
        yield module


def _import_module_names(call: ast.Call, package: list[str]) -> Iterator[str]:
    """The module an import_module call names, with relative names resolved."""
    name = _first_str_arg(call)
    if not call.args:
        name = _constant_str(_keyword_value(call, "name"))

    if not name:
        return

    if not name.startswith("."):
        yield name
        return

    kwarg = _constant_str(_keyword_value(call, "package"))
    if kwarg is None and len(call.args) > 1:
        kwarg = _constant_str(call.args[1])

    rest = name.lstrip(".")
    parts = kwarg.split(".") if kwarg is not None else package
    module = _relative_name(len(name) - len(rest), rest, parts)

    if module is not None:
        yield module


def _import_string_names(call: ast.Call) -> Iterator[str]:
    """The module an import_string call names, with its dotted prefixes."""
    target = _first_str_arg(call)

    if target is not None:
        yield from _dotted_prefixes(target)


def _callee_name(func: ast.AST) -> str | None:
    """The bare name a call invokes, ignoring any object path."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr

    return None


def _first_str_arg(call: ast.Call) -> str | None:
    """The literal string first argument of a call, or None."""
    return _constant_str(call.args[0]) if call.args else None


def _constant_str(node: ast.AST | None) -> str | None:
    """The literal string value of an expression node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    return None


def _keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    """The value node of a call keyword argument, or None."""
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _relative_name(level: int, rest: str | None, package: list[str]) -> str | None:
    """The absolute dotted module that a relative name refers to."""
    keep = len(package) - (level - 1)

    if keep < 0:
        return None

    parts = package[:keep]

    if rest:
        parts.append(rest)

    return ".".join(parts) or None


def _from_base(node: ast.ImportFrom, package: list[str]) -> str | None:
    """Absolute dotted module that a from-import refers to."""
    if not node.level:
        return node.module

    return _relative_name(node.level, node.module, package)


def _dotted_prefixes(dotted: str) -> Iterator[str]:
    """A dotted name and every shorter dotted prefix of it."""
    if not dotted:
        return

    parts = dotted.split(".")

    yield from (".".join(parts[:count]) for count in range(1, len(parts) + 1))


def _get_model_names(call: ast.Call) -> Iterator[str]:
    """The modules an apps.get_model call may import a model from."""
    label = _first_str_arg(call)
    if not call.args:
        label = _constant_str(_keyword_value(call, "app_label"))

    if not label:
        return

    if len(call.args) < 2 and _keyword_value(call, "model_name") is None:
        label = label.split(".")[0]

    yield f"{label}.models"
    yield from _dotted_prefixes(label)


def _override_settings_names(call: ast.Call) -> Iterator[str]:
    """Module names in the literal strings of an override_settings call."""
    values = (*call.args, *(keyword.value for keyword in call.keywords))

    yield from (
        prefix
        for value in values
        for string in _literal_strings(value)
        for prefix in _dotted_prefixes(string)
    )


def _literal_strings(node: ast.AST) -> Iterator[str]:
    """Literal strings in an expression, through containers and dict values."""
    string = _constant_str(node)

    if string is not None:
        yield string
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        yield from (part for elt in node.elts for part in _literal_strings(elt))
    elif isinstance(node, ast.Dict):
        yield from (part for value in node.values for part in _literal_strings(value))
