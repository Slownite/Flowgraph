# Flowgraph v1 design

## Product objective

Flowgraph answers: "Starting from this Python entry point, which local functions can execution reach?" It produces a small, deterministic call-flow graph that is useful for orientation in an unfamiliar repository.

The graph is an honest function-level approximation. It does not claim to identify an application's major semantic stages. Reachability from an entry point, a default depth limit, explicit exclusions, and focused path queries provide the initial noise controls.

Call edges describe invocation ownership, not temporal sequence. If `run_pipeline` calls `extract_features` and then `estimate_pose`, both are children of `run_pipeline`; flowgraph does not add the false edge `extract_features -> estimate_pose`. Edge line numbers preserve call-site order for consumers that want to present ordered children.

## Design decisions

The design was challenged before implementation. The resulting v1 choices are:

- Use Python's built-in `ast`; tree-sitter is not justified for Python-only, syntactically valid source.
- Identify symbols as `relative/path.py:qualified.name`. Source lines are metadata, not identity.
- Resolve only obvious calls: same-module functions, explicit local imports and aliases, module-qualified calls, and `self`/`cls` methods.
- Include only confidently resolved local calls as graph edges. Preserve ambiguous dynamic calls as diagnostics rather than inventing edges.
- Index direct absolute and relative local imports. Do not emulate wildcard imports, dynamic imports, or package re-exports.
- Use plain adjacency traversal rather than NetworkX. V1 needs breadth-first reachability and forward/reverse reachability only.
- Export JSON and Mermaid and print a terminal summary. An interactive HTML application would distract from analyzer quality in v1.
- Offer two workflows: an entry-rooted graph and an all-connecting-flow path query. Separate `analyze`, `graph`, and `inspect` commands would duplicate a small API.
- Limit entry-rooted output to depth 5 by default and support repeatable canonical-ID glob exclusions. Do not hide functions using name-based "utility" heuristics.

## Non-goals

- Perfect Python dispatch, type inference, monkey-patching, decorators, or runtime import emulation
- Calls through arbitrary instances, callbacks, reflection, or values returned by factories
- Standard-library and third-party call nodes
- Semantic stage inference or mandatory LLM use
- Runtime tracing
- Multi-language parsing
- Interactive HTML visualization

## Graph model

A node represents a local function, async function, or method and contains a canonical ID, qualified name, relative file, source range, and kind. A directed edge represents a statically resolved call and contains the caller, callee, call-site line, kind, and confidence.

The JSON document also carries a schema version, analysis metadata, and unresolved call-site diagnostics. The schema leaves room for future optional node summaries/groups and edge evidence such as `static`, `runtime`, or both without changing symbol identity.

Module execution is not modeled as a node in v1. Classes are namespaces for method identity, not graph nodes. Nested functions are indexed with qualified names, although resolution is intentionally conservative.

## Resolution strategy

1. Recursively scan local `.py` files, excluding common generated, virtual-environment, VCS, and output directories.
2. Parse each file and index function and method definitions before resolving any calls.
3. Map file paths to importable module names, including package `__init__.py` files.
4. Collect unconditional direct module imports and direct function-local imports. A function-local import must precede its call site.
5. Resolve bare local names, imported function aliases, local module aliases, and `self`/`cls` method calls.
6. Reject names shadowed by parameters, assignments, loop targets, or conditional imports rather than creating false edges.
7. Mark unsupported calls as diagnostics. Ignore known built-ins and calls through known external imports as expected noise.
8. Traverse only resolved local edges from the selected entry point.

This is intentionally not a Python interpreter. A missing edge is preferable to a confidently displayed false edge.

## CLI UX

```text
flowgraph REPO --entry relative/path.py:qualified.name [--depth 5] [--exclude GLOB]
flowgraph path REPO --from SELECTOR --to SELECTOR [--exclude GLOB]
```

The primary command writes `.flowgraph/graph.json` and `.flowgraph/graph.mmd`. `--output-dir` can change the destination. Selectors may be canonical IDs or unique function/qualified names; ambiguous shorthand is an error with candidate IDs.

Path mode returns the subgraph containing every node that is both reachable from the source and able to reach the target. This preserves alternate branches and merges without enumerating exponentially many paths.

## Known limitations

- Calls such as `object.method()`, callbacks, aliases created by assignment, and most decorator effects are unresolved.
- Import resolution does not execute `__init__.py` re-exports or honor runtime `sys.path` changes.
- Conditional imports are deliberately unresolved because v1 does not prove branch dominance.
- Duplicate/redefined qualified names in one file cannot both have stable IDs; they are reported as analysis errors.
- Calls made by module-level statements and class bodies are not represented.
- Focused call paths do not include earlier or later sibling calls merely because they execute in source order.
- Syntax errors stop analysis with a source-located CLI error.
- The default depth can hide deeper flow; users can increase it explicitly.

## Roadmap

1. Validate the static graph against real repositories and improve resolution only from observed failures.
2. Add optional semantic summaries and stage groups as annotations over stable function IDs. The deterministic graph remains authoritative.
3. Add runtime tracing as separate evidence over the same IDs, allowing static-only, observed, and combined edge states.
4. Consider a self-contained HTML viewer only when JSON and Mermaid no longer support practical exploration.
5. Consider tree-sitter only for concrete multi-language or error-tolerant parsing requirements.
