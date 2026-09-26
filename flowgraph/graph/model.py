from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    name: str
    qualname: str
    file: str
    line: int
    end_line: int
    kind: str


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    line: int
    kind: str = "call"
    confidence: str = "resolved"
    evidence: str = "static"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    caller: str
    file: str
    line: int
    expression: str
    reason: str


@dataclass(slots=True)
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def adjacency(self) -> dict[str, set[str]]:
        result = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            if edge.source in result and edge.target in self.nodes:
                result[edge.source].add(edge.target)
        return result

    def reverse_adjacency(self) -> dict[str, set[str]]:
        result = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            if edge.source in self.nodes and edge.target in result:
                result[edge.target].add(edge.source)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "metadata": self.metadata,
            "nodes": [asdict(self.nodes[node_id]) for node_id in sorted(self.nodes)],
            "edges": [
                asdict(edge)
                for edge in sorted(
                    self.edges, key=lambda item: (item.source, item.target, item.line)
                )
            ],
            "diagnostics": [
                asdict(item)
                for item in sorted(
                    self.diagnostics,
                    key=lambda value: (value.file, value.line, value.expression),
                )
            ],
        }


class SelectorError(ValueError):
    """Raised when a symbol selector is missing or ambiguous."""


def resolve_selector(graph: Graph, selector: str) -> str:
    normalized = selector.replace("\\", "/")
    if normalized in graph.nodes:
        return normalized

    matches = [
        node.id
        for node in graph.nodes.values()
        if node.name == selector or node.qualname == selector
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SelectorError(f"no function matches {selector!r}")

    candidates = ", ".join(sorted(matches))
    raise SelectorError(f"ambiguous function {selector!r}; use one of: {candidates}")
