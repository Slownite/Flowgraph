# Flowgraph

Flowgraph is a small, deterministic CLI for understanding reachable function calls in an unfamiliar Python repository. Starting from one local function, it follows confidently resolved local calls and writes a readable terminal summary, JSON, and Mermaid.

It is a static call-flow explorer, not a dependency graph or Python interpreter. Dynamic dispatch is reported honestly rather than guessed.

## Install

Requires Python 3.10 or newer and is explicitly tested on Python 3.12. The Nix package uses Python 3.12. The runtime has no third-party dependencies.

```bash
pipx install git+https://github.com/Slownite/Flowgraph.git
flowgraph --help
```

Run directly with uv without installing:

```bash
uvx --from git+https://github.com/Slownite/Flowgraph.git flowgraph --help
```

Install or run with Nix:

```bash
nix profile install github:Slownite/Flowgraph
nix run github:Slownite/Flowgraph -- --help
```

## Use

Analyze only local functions reachable within five calls of an entry point:

```bash
flowgraph ./my_repo --entry app.py:main
```

Increase depth and hide utility modules with canonical-ID globs:

```bash
flowgraph ./my_repo \
  --entry app.py:main \
  --depth 8 \
  --exclude 'utils/*.py:*'
```

Focus on every resolved caller/callee route connecting two functions:

```bash
flowgraph path ./my_repo \
  --from app.py:main \
  --to geometry.py:estimate_pose
```

Unique function names such as `--from main` can be used as shorthand. Ambiguous names produce an error listing canonical IDs.

By default, output is written inside the analyzed repository:

```text
.flowgraph/graph.json
.flowgraph/graph.mmd
```

Use `--output-dir PATH` to choose another location.

## Resolution

Flowgraph resolves:

- functions in the same module
- direct absolute and relative local imports, including aliases
- calls qualified by imported local modules
- obvious `self.method()`, `cls.method()`, and explicit class-method calls
- nested lexical functions where the binding is direct

It excludes standard-library and third-party calls. Calls through arbitrary objects, callbacks, reflection, wildcard imports, dynamic imports, assignment aliases, and package re-exports remain unresolved and appear as diagnostics in JSON.

Call edges represent invocation ownership, not temporal sequence. If `pipeline()` calls `read()` and then `process()`, both are children of `pipeline()`; source line metadata records their order without inventing a false `read -> process` edge.

See [`docs/design.md`](docs/design.md) for the model, tradeoffs, limitations, and runtime/semantic-layer roadmap.

## Develop

```bash
git clone https://github.com/Slownite/Flowgraph.git
cd Flowgraph
uv run --extra test pytest
nix flake check
```

The test suite includes a multi-file pipeline fixture and a package fixture covering relative imports and methods.

## Agent Skill

Install the Flowgraph skill globally for OpenCode, Codex, and Claude Code:

```bash
npx skills add Slownite/Flowgraph \
  --skill flowgraph \
  --global \
  --agent opencode codex claude-code
```

Omit `--global` to install it in the current project. The skill uses the shared Agent Skills format and teaches agents to choose entry points, run focused analyses, and interpret unresolved calls without overstating static results. Restart an agent after installation if it does not reload skills automatically.
