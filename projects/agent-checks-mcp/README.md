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
