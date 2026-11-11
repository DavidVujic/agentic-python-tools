"""Test tools: argvs and config markers."""

from agenticpytools.checks.tools import Tool, dependency_names, normalize_dep_name

TEST_TOOLS: dict[str, Tool] = {
    "pytest": {
        "argvs": [[]],
        "sections": ["tool.pytest.ini_options"],
        "ini_sections": ["pytest", "tool:pytest"],
        "files": ["pytest.ini"],
    },
    "tox": {
        "argvs": [[]],
        "ini_sections": ["testenv"],
        "files": ["tox.ini"],
    },
    "nox": {"argvs": [[]], "files": ["noxfile.py"]},
}

__all__ = ["TEST_TOOLS", "Tool", "dependency_names", "normalize_dep_name"]
