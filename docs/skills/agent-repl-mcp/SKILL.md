---
name: agent-repl-mcp
description: Use for REPL-driven Python work with the agent-python-repl-mcp server (behavior of a function, library call, data shape, edge case, or a change to it) when running code in a live process answers faster than reading. Assumes the server is already configured in the agent harness. Covers sessions and kernel lifecycle, the edit-and-verify cycle, fakes instead of real I/O, and normal exceptions vs MCP or kernel failures.
---

# Agent REPL MCP Skill

The `agent-python-repl-mcp` server provides a persistent Python REPL: one Jupyter kernel per project and session.

## When to use

- The behavior of a function, library call, or data shape is unclear, and running code with representative inputs answers it faster than reading.
- You are about to edit project code and want to try a change and verify it in a live process first.
- Skip it when reading the code already answers the question, and for documentation, config, or trivial changes. Never install or modify dependencies to make the REPL work.

## Sessions

- `session_id` is any non-empty string, stable for the whole agent session and unique among concurrent sessions. Prefer the host's chat or session ID; otherwise generate a UUIDv4 once with a real generator. Never fabricate one from the project or task.
- Pass the same `session_id` and absolute `project_full_path` to every `run` and `close`; a different pair starts a different kernel. The kernel uses the project's `.venv`, so the path must point to a project with one, else `run` fails with "No virtual environment found".
- State (imports, definitions, values) persists between `run` calls: import once and reuse, and send small snippets rather than long scripts. `run` returns `stdout`, `stderr`, `result`, and `error`; on timeout `error` says "Timeout: try again."
- Keep the kernel alive while working. Call `close(project_full_path, session_id)` when finished — also after a failed or abandoned last experiment — or to deliberately reset state, e.g. when results contradict the source code (an in-memory redefinition may be shadowing it). After `close`, the next `run` starts a fresh kernel.

## Edit-and-verify

1. Set up fakes (below), import the code under test, reproduce the behavior with representative inputs.
2. Try changes as in-memory redefinitions, evaluated against the same inputs. They never modify source files: persist a successful one with the normal edit tools.
3. Verify the saved implementation in the same kernel, setting up fakes again. `importlib.reload` misses existing references (`from x import y`, instances, closures), so re-fetch what you call. If results still contradict the source after a `close` + `run` reset, the source on disk is what ran — report it.

## No real I/O

- Replace databases, files, network, subprocesses, queues, and services with the project's existing fakes or mocks, or a simple in-memory fake (`unittest.mock`, a dict). Loading Python modules is fine.
- Never install dependencies for the REPL. Ask the user when a safe fake is not possible.

## Errors

- A Python exception raised by your experiment is normal output; read it and continue.
- Tool errors, a dead or hung kernel, or lost state are not: report the call made and the expected versus actual result, without secrets. Do not silently fall back to `python -c` without saying so.

## Limits

- The REPL does not replace regression tests, lint, or unit tests.
