"""Unit tests for running detected commands as subprocesses."""

import json
import os
import sys
from types import SimpleNamespace

import pytest
from agenticpytools.runner import run_commands
from agenticpytools.runner.core import _child_env

pytestmark = pytest.mark.runner


def _python_command(code: str, **extra: object) -> dict:
    """A command dict running code with the current interpreter."""
    return {"argv": [sys.executable, "-c", code], "cwd": None, **extra}


def test_success():
    results = run_commands([_python_command("print('hi')")])

    assert results[0]["returncode"] == 0
    assert results[0]["stdout"] == "hi\n"


def test_failure():
    results = run_commands([_python_command("import sys; sys.exit(3)")])

    assert results[0]["returncode"] == 3


def test_stderr_captured():
    results = run_commands([_python_command("import sys; sys.stderr.write('e')")])

    assert results[0]["stderr"] == "e"


def test_cwd_respected(tmp_path):
    command = _python_command("import os; print(os.getcwd())", cwd=str(tmp_path))

    results = run_commands([command])

    assert results[0]["stdout"].strip() == os.path.realpath(tmp_path)


def test_child_env_strips_activation_vars(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/agent/venv")
    monkeypatch.setenv("PYTHONPATH", "/agent/src")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "/agent/conda")
    monkeypatch.setenv("POETRY_VIRTUALENVS_PATH", "/agent/poetry")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/agent/uv")
    monkeypatch.setenv("KEEP_ME", "1")

    code = (
        "import os, json; print(json.dumps({"
        "k: os.environ.get(k) for k in "
        "['VIRTUAL_ENV', 'PYTHONPATH', 'CONDA_DEFAULT_ENV', "
        "'POETRY_VIRTUALENVS_PATH', 'UV_PROJECT_ENVIRONMENT', 'KEEP_ME']}))"
    )
    results = run_commands([_python_command(code)])

    env = json.loads(results[0]["stdout"])
    assert env["VIRTUAL_ENV"] is None
    assert env["PYTHONPATH"] is None
    assert env["CONDA_DEFAULT_ENV"] is None
    assert env["POETRY_VIRTUALENVS_PATH"] is None
    assert env["UV_PROJECT_ENVIRONMENT"] is None
    assert env["KEEP_ME"] == "1"


def test_child_env_uses_project_venv(tmp_path, monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/agent/venv")
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)

    env = _child_env(str(tmp_path))

    assert env["VIRTUAL_ENV"] == str(venv)
    assert env["PATH"].startswith(str(venv / "bin"))


def _captured_env(monkeypatch, command: dict) -> dict:
    """The env subprocess.run received for one command."""
    captured: list[dict] = []

    def fake_run(argv, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("agenticpytools.runner.core.subprocess.run", fake_run)
    run_commands([command])

    return captured[0]["env"]


def test_run_commands_env_puts_project_venv_bin_on_path(tmp_path, monkeypatch):
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)

    env = _captured_env(monkeypatch, _python_command("pass", cwd=str(tmp_path)))

    assert env["VIRTUAL_ENV"] == str(venv)
    assert env["PATH"].startswith(str(venv / "bin"))


def test_run_commands_env_stripped_without_project_venv(tmp_path, monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/agent/venv")

    no_cwd = _captured_env(monkeypatch, _python_command("pass"))
    no_venv = _captured_env(monkeypatch, _python_command("pass", cwd=str(tmp_path)))

    assert "VIRTUAL_ENV" not in no_cwd
    assert "VIRTUAL_ENV" not in no_venv
    assert no_cwd.get("PATH") == os.environ.get("PATH")
    assert no_venv.get("PATH") == os.environ.get("PATH")


def test_files_appended_when_tool_takes_files():
    command = _python_command("import sys; print(sys.argv[1:])", takes_files=True)

    results = run_commands([command], files=["a.py", "b.py"])

    assert results[0]["stdout"].strip() == "['a.py', 'b.py']"


def _echo_args_command(*args: str) -> dict:
    """A takes-files command printing its args, with '.' as its project args."""
    code = "import sys; print(sys.argv[1:])"
    argv = [sys.executable, "-c", code, *args]

    return {"argv": argv, "cwd": None, "takes_files": True, "project_args": ["."]}


def test_project_args_replaced_by_files():
    results = run_commands([_echo_args_command("--check", ".")], files=["a.py"])

    assert results[0]["stdout"].strip() == "['--check', 'a.py']"
    assert results[0]["argv"][-2:] == ["--check", "a.py"]


@pytest.mark.parametrize("files", [None, []], ids=["none", "empty"])
def test_project_args_kept_without_files(files):
    results = run_commands([_echo_args_command("--check", ".")], files=files)

    assert results[0]["stdout"].strip() == "['--check', '.']"


def test_project_args_not_stripped_when_not_trailing():
    results = run_commands([_echo_args_command(".", "src")], files=["a.py"])

    assert results[0]["stdout"].strip() == "['.', 'src', 'a.py']"


def test_files_not_appended_without_takes_files():
    code = "import sys; print(sys.argv[1:])"
    commands = [_python_command(code), _python_command(code, takes_files=False)]

    results = run_commands(commands, files=["a.py"])

    assert [r["stdout"].strip() for r in results] == ["[]", "[]"]


def test_missing_binary():
    results = run_commands([{"argv": ["definitely-not-a-real-binary-xyz"]}])

    assert results[0]["returncode"] == 127
    assert "command not found" in results[0]["stderr"]


def test_timeout():
    command = _python_command("import time; time.sleep(5)")

    results = run_commands([command], timeout=0.2)

    assert results[0]["returncode"] == 124


def test_order_preserved():
    commands = [_python_command("print('first')"), _python_command("print('second')")]

    results = run_commands(commands)

    assert [r["stdout"].strip() for r in results] == ["first", "second"]
