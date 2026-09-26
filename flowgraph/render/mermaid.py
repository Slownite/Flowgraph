from __future__ import annotations

from flowgraph.graph.model import Graph


def render_mermaid(graph: Graph) -> str:
    node_names = {
        node_id: f"n{position}" for position, node_id in enumerate(sorted(graph.nodes))
    }
    lines = ["flowchart TD"]
    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        label = f"{node.qualname}()<br/>{node.file}:{node.line}"
        label = label.replace('"', "&quot;")
        lines.append(f'    {node_names[node_id]}["{label}"]')
    seen: set[tuple[str, str]] = set()
    for edge in sorted(graph.edges, key=lambda item: (item.source, item.target)):
        pair = (edge.source, edge.target)
        if pair in seen:
            continue
        seen.add(pair)
        lines.append(f"    {node_names[edge.source]} --> {node_names[edge.target]}")
    return "\n".join(lines) + "\n"
