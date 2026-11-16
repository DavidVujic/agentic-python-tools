"""Run detected command dicts as subprocesses."""

import os
import subprocess


def run_commands(
    commands: list[dict], files: list[str] | None = None, timeout: float = 60.0
) -> list[dict]:
    """Run each command, appending changed files when the tool takes them."""
    return [_run_one(cmd, files, timeout) for cmd in commands]


def _argv(cmd: dict, files: list[str] | None) -> list[str]:
    """The command's argv, with changed files replacing its declared project args."""
    argv = list(cmd["argv"])

    if not (files and cmd.get("takes_files")):
        return argv

    project_args = list(cmd.get("project_args", []))
    size = len(project_args)

    if size and argv[-size:] == project_args:
        argv = argv[:-size]

    return argv + [str(f) for f in files]


def _run_one(cmd: dict, files: list[str] | None, timeout: float) -> dict:
    """One command's result: argv, returncode, stdout, and stderr."""
    argv = _argv(cmd, files)

    try:
        proc = subprocess.run(
            argv,
            cwd=cmd.get("cwd"),
            env=_child_env(),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
        return _result(argv, proc.returncode, proc.stdout, proc.stderr)
    except FileNotFoundError:
        return _result(argv, 127, "", f"command not found: {argv[0]}")
    except subprocess.TimeoutExpired as exc:
        stderr = _decoded(exc.stderr) or f"timed out after {timeout}s"

        return _result(argv, 124, _decoded(exc.stdout), stderr)


STRIPPED_ENV_VARS = frozenset(
    {
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "PYTHONHOME",
        "PYTHONPATH",
        "POETRY_VIRTUALENVS_PATH",
        "UV_PROJECT_ENVIRONMENT",
    }
)


def _child_env() -> dict:
    """Environment for child tools: the caller's activated venv must not leak into the target project."""
    return {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV_VARS}


def _result(argv: list[str], returncode: int, stdout: str, stderr: str) -> dict:
    """A command's result dict."""
    return {
        "argv": argv,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def _decoded(output: str | bytes | None) -> str:
    """Partial timeout output as text; bytes are decoded, None is empty."""
    if isinstance(output, bytes):
        return output.decode()

    return output or ""


def summarize(results: list[dict]) -> list[str]:
    """One status line per result, e.g. 'ok (0): ruff check'."""
    return [
        f"{'ok' if r['returncode'] == 0 else 'FAIL'}"
        f" ({r['returncode']}): {' '.join(r['argv'])}"
        for r in results
    ]
