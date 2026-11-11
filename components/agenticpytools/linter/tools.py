"""Linter tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name

LINTERS: dict[str, Tool] = {
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
}

__all__ = ["LINTERS", "Tool", "dependency_names", "normalize_dep_name"]
