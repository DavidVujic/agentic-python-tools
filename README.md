# Agentic Python Tools

A repo containing tools for Agentic Engineering with Python.

[![CircleCI](https://dl.circleci.com/status-badge/img/gh/DavidVujic/agentic-python-tools/tree/main.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/DavidVujic/agentic-python-tools/tree/main)

[![CodeScene Average Code Health](https://codescene.io/projects/87469/status-badges/average-code-health)](https://codescene.io/projects/87469)

[![Quality gate status](https://sonarcloud.io/api/project_badges/measure?project=DavidVujic_agentic-python-tools&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=DavidVujic_agentic-python-tools)

## Agent REPL MCP

__Status__: Work in progress

A Python REPL that agents can use during development.

The REPL MCP gives agents a persistent Python REPL. Each agent session gets its own Jupyter kernel per project that stays alive across calls, so state like imports and variables carries over. The `session_id` is any non-empty string that is stable for the whole agent session and unique among concurrent sessions: prefer an existing chat or session ID from the host, and fall back to a UUID generated once only if there is none. Your agent sends code with `run(data, project_full_path, session_id)` and ends the session with `close(project_full_path, session_id)`. Edits to real source files are picked up automatically on the next run.

### Installation

``` shell
pip install agent-repl-mcp
```

### Add it to your Agent tool

#### Example: using `uvx`
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

#### Demo
![Agent REPL MCP in action](docs/images/agent-repl-mcp.gif)
