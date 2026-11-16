"""Type checker tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool

TYPE_CHECKERS: dict[str, Tool] = {
    "mypy": {
        "argvs": [["."]],
        "sections": ["tool.mypy"],
        "ini_sections": ["mypy"],
        "files": ["mypy.ini", ".mypy.ini"],
        "takes_files": True,
        "project_args": ["."],
    },
    "ty": {"argvs": [["check"]], "sections": ["tool.ty"], "takes_files": True},
    "pyright": {"argvs": [[]], "sections": ["tool.pyright"], "takes_files": True},
}
