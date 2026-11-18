# Agent Checks MCP

An MCP server that watches a project and serves cached lint, typecheck, and test results.

The Checks MCP watches a project in the background and keeps lint, typecheck, and test results up to date, so your agent gets them instantly instead of waiting for each run. Each tool takes a `project_full_path` and a `session_id`.

On each change it will run _lint_ and _type checks_ for the changed code, and the affected _tests_.

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
