"""Run detected command dicts as subprocesses."""

import subprocess


def run_commands(
    commands: list[dict], files: list[str] | None = None, timeout: float = 60.0
) -> list[dict]:
    """Run each command, appending changed files when the tool takes them."""
    return [_run_one(cmd, files, timeout) for cmd in commands]


def _run_one(cmd: dict, files: list[str] | None, timeout: float) -> dict:
    """One command's result: argv, returncode, stdout, and stderr."""
    argv = list(cmd["argv"])

    if files and cmd.get("takes_files"):
        argv += [str(f) for f in files]

    try:
        proc = subprocess.run(
            argv,
            cwd=cmd.get("cwd"),
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
