"""Test tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name

TEST_TOOLS: dict[str, Tool] = {
    "pytest": {
        "argvs": [[]],
        "sections": ["tool.pytest.ini_options"],
        "ini_sections": ["pytest", "tool:pytest"],
        "files": ["pytest.ini"],
        "takes_files": False,
    },
    "tox": {
        "argvs": [[]],
        "ini_sections": ["testenv"],
        "files": ["tox.ini"],
        "takes_files": False,
    },
    "nox": {"argvs": [[]], "files": ["noxfile.py"], "takes_files": False},
}

__all__ = ["TEST_TOOLS", "Tool", "dependency_names", "normalize_dep_name"]
