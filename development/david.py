from pathlib import Path

from agenticpytools import storage
from agenticpytools.repl_mcp import core

project_full_path = (Path.cwd().parent / "python-hiccup").as_posix()
project_name = "python-repl-mcp"


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
    return core.run(data, project_full_path)


def list():
    return storage.list_entries()


def close():
    return core.close(project_full_path)
