"""Linter tools: argvs, config markers, and dependency-name helpers."""

import re
from typing import TypedDict


class Linter(TypedDict, total=False):
    """One linter's run args and config markers; every key has a default."""

    module: str
    argvs: list[list[str]]
    sections: list[str]
    section_prefixes: list[str]
    ini_sections: list[str]
    files: list[str]


LINTERS: dict[str, Linter] = {
    "ruff": {
        "argvs": [["check"], ["format", "--check"]],
        "sections": ["tool.ruff"],
        "files": ["ruff.toml", ".ruff.toml"],
    },
    "flake8": {"argvs": [[]], "ini_sections": ["flake8"], "files": [".flake8"]},
    "pylint": {
        "argvs": [["."]],
        "section_prefixes": ["tool.pylint"],
        "files": [".pylintrc", "pylintrc"],
    },
    "black": {"argvs": [["--check", "."]], "sections": ["tool.black"]},
    "isort": {"argvs": [["--check-only", "."]], "sections": ["tool.isort"]},
    "mypy": {
        "argvs": [["."]],
        "sections": ["tool.mypy"],
        "ini_sections": ["mypy"],
        "files": ["mypy.ini", ".mypy.ini"],
    },
    "ty": {"argvs": [["check"]], "sections": ["tool.ty"]},
    "pyright": {"argvs": [[]], "sections": ["tool.pyright"]},
}


def normalize_dep_name(dep: str) -> str:
    """PEP 503-normalized dependency name, without extras or specifiers."""
    match = re.match(r"[A-Za-z0-9._-]+", dep.strip())
    name = match.group(0) if match else ""

    return re.sub(r"[-_.]+", "-", name.lower())


def dependency_names(data: dict) -> list[str]:
    """PEP 503-normalized dependency names declared in a parsed pyproject."""
    project = data.get("project", {})
    poetry = data.get("tool", {}).get("poetry", {})
    optional = project.get("optional-dependencies", {})
    poetry_groups = poetry.get("group", {})

    deps = [
        *(dep for group in data.get("dependency-groups", {}).values() for dep in group),
        *project.get("dependencies", []),
        *(dep for group in optional.values() for dep in group),
        *poetry.get("dependencies", {}),
        *(
            dep
            for group in poetry_groups.values()
            for dep in group.get("dependencies", {})
        ),
    ]

    return [normalize_dep_name(dep) for dep in deps if isinstance(dep, str)]
