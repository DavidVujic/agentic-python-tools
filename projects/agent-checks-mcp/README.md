# Agent Checks MCP

An MCP server that watches a project and serves lint, typecheck, and test results.

The Agent Checks MCP is built to make the code verification process faster and with less frustration. Without human interaction,
it will analyze the codebase to figure out the setup and will find the commands for linting, type checking and testing - without the need of any Agent instructions.

The MCP takes the burden off the Agent. It watches a project in the background and keeps lint, typecheck, and test results up to date,
so your agent gets them instantly instead of having to wait for each run. Each tool takes a `project_full_path` and a `session_id`.

On each file change it will run _lint_ and _type checks_ for the changed code, and the affected _tests_.

Agent Checks MCP has support for the major Python linting and type checking tools, and pytest.

## Setup

### Add the MCP server to your harness

#### Example: using `uvx`
``` json
{
  "mcpServers": {
    "agent-checks-mcp": {
      "command": "uvx",
      "args": ["agent-checks-mcp"]
    }
  }
}
```

or install it:
``` shell
pip install agent-checks-mcp
```

## Figuring out the setup
For each check, it tries these places in order and stops at the first one that has a command:

1. **justfile**: recipe named `lint`, `typecheck`/`type-check`/`types`, or `test`/`tests` (needs `just` installed)
2. **Makefile**: same-named target (needs `make`)
3. **pyproject tasks**: poe, then pixi, then hatch
4. **pyproject tools**: tool listed as a dependency or with a config section/marker file; one command per tool's argv variant, in table order (ruff → flake8 → pylint → black → isort; mypy → ty → pyright; pytest → tox → nox)
5. **venv**: any of those tools actually installed in `.venv`, run as `<venv-python> -m <module>`

The first place that has a command decides the full command, used by the initial and on-demand runs. When it is a recipe without file arguments (`just`, `make`, poe, pixi, or hatch), a secondary file-scoped command is also detected from the deeper places in the ladder, from the first tool that accepts file paths (such as ruff, ty, or pytest). The watcher batches run that file-scoped command with the changed files appended, or the affected tests for the test check; files from the kind's previous run follow the upcoming watcher batches, so the reported changed files cover all files changed so far.

Detected commands run with the project as working directory and, when the project has a `.venv`, with that venv's bin directory on `PATH` (so `just lint` / `make lint` recipes resolve tools from the project venv).

## Skills
Copy the [Agent Checks MCP ](https://github.com/DavidVujic/agentic-python-tools/blob/main/docs/skills/agent-checks-mcp/SKILL.md) skill to your setup and modify it as you like.
