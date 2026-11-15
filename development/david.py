import uuid
from pathlib import Path

from agenticpytools import storage
from agenticpytools.checks_mcp import core as checks_mcp
from agenticpytools.repl_mcp import core as repl_mcp

hiccup_full_path = (Path.cwd().parent / "python-hiccup").as_posix()
poly_full_path = (Path.cwd().parent / "python-polylith").as_posix()
project_name = "python-repl-mcp"
session_id = str(uuid.uuid4())


data = """
x = 3
y = 4
from python_hiccup.html import raw, render

def helloworld():
    print(render(['div', 'helloworld']))
    return x + y

helloworld()
"""

"""
shell commands

Current running kernels
ps aux | grep "[i]pykernel"

Kill all running kernels
pkill -f ipykernel

List kernel storage
ls /Users/$(whoami)/Library/Jupyter/runtime/

Cleanup kernel storage
rm /Users/$(whoami)/Library/Jupyter/runtime/*.json
rm /Users/$(whoami)/Library/Jupyter/runtime/kernel-*-ipc-*


Agent config during dev:
{
  "mcpServers": {
    "python-repl-mcp": {
      "command": "python",
      "args": ["/Users/$(whoami)/github/agentic-python-tools/bases/agenticpytools/repl_mcp/core.py"]
    }
  }
}


Check the DB:
sqlite3 "$HOME/.python-repl-mcp/kernels.db" 'SELECT count(*) FROM kernels;'

Clear the DB:
sqlite3 "$HOME/.python-repl-mcp/kernels.db" 'DELETE FROM kernels;'
"""


def run():
    return repl_mcp.run(data, hiccup_full_path, session_id)


def list():
    return storage.list_entries()


def close():
    return repl_mcp.close(hiccup_full_path, session_id)


def start_checks(path: str):
    return checks_mcp.start_watching(path, session_id)


def stop_checks(path: str):
    return checks_mcp.stop_watching(path, session_id)


def lint_results(path: str):
    return checks_mcp.lint(path, session_id)


def typecheck_results(path: str):
    return checks_mcp.typecheck(path, session_id)


def test_results(path: str):
    return checks_mcp.test(path, session_id)


def check_commands(path: str):
    return checks_mcp.detected_commands(path, session_id)
