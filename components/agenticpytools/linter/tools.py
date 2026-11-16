"""Linter tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name

LINTERS: dict[str, Tool] = {
    "ruff": {
        "argvs": [["check"], ["format", "--check"]],
        "sections": ["tool.ruff"],
        "files": ["ruff.toml", ".ruff.toml"],
        "takes_files": True,
    },
    "flake8": {
        "argvs": [[]],
        "ini_sections": ["flake8"],
        "files": [".flake8"],
        "takes_files": True,
    },
    "pylint": {
        "argvs": [["."]],
        "section_prefixes": ["tool.pylint"],
        "files": [".pylintrc", "pylintrc"],
        "takes_files": True,
        "project_args": ["."],
    },
    "black": {
        "argvs": [["--check", "."]],
        "sections": ["tool.black"],
        "takes_files": True,
        "project_args": ["."],
    },
    "isort": {
        "argvs": [["--check-only", "."]],
        "sections": ["tool.isort"],
        "takes_files": True,
        "project_args": ["."],
    },
}

__all__ = ["LINTERS", "Tool", "dependency_names", "normalize_dep_name"]
