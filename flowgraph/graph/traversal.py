from __future__ import annotations

from collections import deque
from fnmatch import fnmatch
from typing import Iterable

from flowgraph.graph.model import Graph


def without_excluded(graph: Graph, patterns: Iterable[str]) -> Graph:
    patterns = tuple(patterns)
    if not patterns:
        return graph
    kept = {
        node_id: node
        for node_id, node in graph.nodes.items()
        if not any(fnmatch(node_id, pattern) for pattern in patterns)
    }
    return _subgraph(
        graph,
        set(kept),
        {"excluded": list(patterns)},
    )


def reachable_graph(graph: Graph, entry: str, depth: int) -> Graph:
    if depth < 0:
        raise ValueError("depth must be zero or greater")
    adjacency = graph.adjacency()
    distances = {entry: 0}
    queue = deque([entry])
    while queue:
        source = queue.popleft()
        if distances[source] >= depth:
            continue
        for target in sorted(adjacency.get(source, ())):
            if target not in distances:
                distances[target] = distances[source] + 1
                queue.append(target)
    return _subgraph(
        graph,
        set(distances),
        {"entry": entry, "depth": depth, "distances": distances},
    )


def connecting_graph(graph: Graph, source: str, target: str) -> Graph:
    forward = _walk(graph.adjacency(), source)
    if target not in forward:
        raise ValueError(f"no resolved call flow from {source} to {target}")
    backward = _walk(graph.reverse_adjacency(), target)
    included = forward & backward
    return _subgraph(
        graph,
        included,
        {"from": source, "to": target, "mode": "all-connecting-flow"},
    )


def _walk(adjacency: dict[str, set[str]], start: str) -> set[str]:
    visited: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, ()) - visited)
    return visited


def _subgraph(graph: Graph, included: set[str], metadata: dict[str, object]) -> Graph:
    return Graph(
        nodes={node_id: graph.nodes[node_id] for node_id in sorted(included)},
        edges=[
            edge
            for edge in graph.edges
            if edge.source in included and edge.target in included
        ],
        diagnostics=[
            diagnostic
            for diagnostic in graph.diagnostics
            if diagnostic.caller in included
        ],
        metadata={**graph.metadata, **metadata},
    )
