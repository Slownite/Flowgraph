from __future__ import annotations

from flowgraph.graph.model import Graph


def render_text(graph: Graph) -> str:
    if not graph.nodes:
        return "No functions in graph."

    adjacency = graph.adjacency()
    entry = graph.metadata.get("entry") or graph.metadata.get("from")
    lines = [
        f"Flowgraph: {len(graph.nodes)} functions, {len(graph.edges)} resolved calls"
    ]
    if entry:
        lines.append(f"Starting at {entry}")
    for source in _display_order(graph):
        node = graph.nodes[source]
        lines.append(f"{node.id} ({node.kind}, line {node.line})")
        targets = sorted(adjacency[source])
        if not targets:
            lines.append("  -> [end or unresolved/external calls]")
        else:
            lines.extend(f"  -> {target}" for target in targets)
    if graph.diagnostics:
        lines.append(
            f"{len(graph.diagnostics)} dynamic/unresolved call sites retained in JSON"
        )
    return "\n".join(lines)


def _display_order(graph: Graph) -> list[str]:
    distances = graph.metadata.get("distances")
    if isinstance(distances, dict):
        return sorted(graph.nodes, key=lambda node_id: (distances.get(node_id, 0), node_id))
    return sorted(graph.nodes)
