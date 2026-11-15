# Agent Checks MCP

Status: WIP, not ready for usage (yet)

An MCP server that watches a project and serves cached lint, typecheck, and test results.

The Checks MCP watches a project in the background and keeps lint, typecheck, and test results up to date, so your agent gets them instantly instead of waiting for each run. Each tool takes a `project_full_path` and a `session_id`:

- `start_watching` — start watching a project; returns its commands and initial check results.
- `detected_commands` — the lint, typecheck, and test commands for a watched session, detected on demand otherwise.
- `lint` — latest cached lint results for the session; runs lint on demand if not ready.
- `typecheck` — latest cached typecheck results for the session; runs typecheck on demand if not ready.
- `test` — latest cached test results for the session; runs the tests on demand if not ready.
- `stop_watching` — stop watching a project session; the watcher thread exits.

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
