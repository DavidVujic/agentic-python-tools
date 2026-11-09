# Agentic Python Tools

A repo containing tools for Agentic Engineering with Python.

[![CircleCI](https://dl.circleci.com/status-badge/img/gh/DavidVujic/agentic-python-tools/tree/main.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/DavidVujic/agentic-python-tools/tree/main)

[![CodeScene Average Code Health](https://codescene.io/projects/87469/status-badges/average-code-health)](https://codescene.io/projects/87469)

[![Quality gate status](https://sonarcloud.io/api/project_badges/measure?project=DavidVujic_agentic-python-tools&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=DavidVujic_agentic-python-tools)

## Agent REPL MCP

A Python REPL that agents can use during development.

The REPL MCP gives agents a persistent Python REPL. Each agent session gets its own Jupyter kernel per project that stays alive across calls.  Your agent sends code with `run(data, project_full_path, session_id)` and ends the session with `close(project_full_path, session_id)`. Edits to real source files are picked up automatically on the next run, using the built-in features of the kernel.

Having a persistent REPL will make the __REPL Driven Development__ workflow possible for your agent. The agent can try out and run small portions of code when it need to verify or figure out things, instead of running complex bash calls.

## Setup
The MCP server is built to be used with your harness, and should support all tools that can add MCP Servers.

### Add the MCP server to your harness

Example: using `uvx`:
``` json
{
  "mcpServers": {
    "agent-repl-mcp": {
      "command": "uvx",
      "args": ["agent-repl-mcp"]
    }
  }
}
```

or install it:
``` shell
pip install agent-repl-mcp
```

### Configure the kernel
Add this to the global IPython configuration (that is also used by Jupyter kernel) to enable auto-reload of changed modules.

``` shell
c.InteractiveShellApp.extensions = ['autoreload']
c.InteractiveShellApp.exec_lines = ['%autoreload 2']
```

How to create and edit [IPython config files](https://ipython.readthedocs.io/en/stable/config/intro.html#python-configuration-files)

## Skills
Copy the [Agent REPL MCP ](./docs/skills/agent-repl-mcp/SKILL.md) skill to your setup and modify it as you like.

## Demo
![Agent REPL MCP in action](docs/images/agent-repl-mcp.gif)
