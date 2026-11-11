"""Type checker tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name

TYPE_CHECKERS: dict[str, Tool] = {
    "mypy": {
        "argvs": [["."]],
        "sections": ["tool.mypy"],
        "ini_sections": ["mypy"],
        "files": ["mypy.ini", ".mypy.ini"],
    },
    "ty": {"argvs": [["check"]], "sections": ["tool.ty"]},
    "pyright": {"argvs": [[]], "sections": ["tool.pyright"]},
}

__all__ = ["TYPE_CHECKERS", "Tool", "dependency_names", "normalize_dep_name"]
