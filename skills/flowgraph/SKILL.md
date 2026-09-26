---
name: flowgraph
description: Maps reachable local Python function calls and focused caller-to-callee flow with Flowgraph. Use when exploring an unfamiliar Python codebase, tracing execution from an entry point, finding possible paths between functions, or reducing call-graph noise.
---

# Flowgraph

Use Flowgraph to establish the static execution-flow skeleton before reading implementation details broadly.

## Quick Start

Analyze a Python repository without installing Flowgraph:

```bash
uvx --from git+https://github.com/Slownite/explore.git flowgraph /path/to/repo --entry relative/file.py:qualified.name
```

If Flowgraph is installed, use `flowgraph` directly. Nix users can run:

```bash
nix run github:Slownite/explore -- /path/to/repo --entry app.py:main
```

## Workflow

1. Locate likely entry functions from CLI entry points, `__main__` blocks, framework configuration, or user-provided context.
2. Run the entry-rooted graph at the default depth of 5.
3. Read the terminal summary first, then `.flowgraph/graph.json` for source locations and unresolved-call diagnostics.
4. Increase `--depth` only when the current frontier is relevant.
5. Use repeatable `--exclude 'glob'` options for known utility or generated modules; do not hide code solely because its function name looks trivial.
6. Use path mode to isolate all resolved call routes between two symbols:

```bash
flowgraph path /path/to/repo --from app.py:main --to package/worker.py:execute
```

7. Open the referenced source locations to validate assumptions before changing code.

## Interpretation Rules

- Treat edges as possible static caller-to-callee relationships, not proof that a call executes at runtime.
- Treat sibling callees as calls owned by the same caller, not as a temporal chain. Edge line numbers preserve source order.
- Treat missing dynamic-dispatch edges as unknown, not absent behavior. Inspect JSON `diagnostics` for callbacks and unresolved object methods.
- Standard-library and third-party calls are intentionally omitted.
- Unique names can be selectors, but canonical `relative/path.py:qualified.name` IDs avoid ambiguity.
- Do not present Flowgraph output as semantic stage grouping; derive stage labels separately and retain links to actual function IDs.

## Outputs

- `.flowgraph/graph.json`: authoritative machine-readable graph and diagnostics
- `.flowgraph/graph.mmd`: Mermaid visualization
- stdout: compact human-readable adjacency summary

When results look wrong, report the smallest reproducing Python construct rather than compensating with guessed edges.
