from flowgraph.graph.model import Diagnostic, Edge, Graph, Node
from flowgraph.render.html import _layout, render_html


def test_renders_self_contained_interactive_html():
    graph = Graph(
        nodes={
            "app.py:main": Node(
                "app.py:main", "main", "main", "app.py", 1, 3, "function"
            ),
            "worker.py:run": Node(
                "worker.py:run", "run", "run", "worker.py", 4, 8, "function"
            ),
        },
        edges=[Edge("app.py:main", "worker.py:run", 2)],
        diagnostics=[
            Diagnostic("worker.py:run", "worker.py", 7, "callback", "dynamic call")
        ],
        metadata={"entry": "app.py:main"},
    )

    document = render_html(graph)

    assert document.startswith("<!doctype html>\n")
    assert '<svg id="graph"' in document
    assert 'id="graph-search"' in document
    assert 'id="zoom-in"' in document
    assert 'id="zoom-out"' in document
    assert 'id="fit-graph"' in document
    assert 'id="details"' in document
    assert 'data-node-id="app.py:main"' in document
    assert 'data-source="app.py:main" data-target="worker.py:run"' in document
    assert 'id="graph-data"' in document
    assert "callback" in document
    assert "https://" not in document
    assert "http://" not in document
    assert "opacity: .28" in document
    assert "mouseenter" in document


def test_escapes_labels_and_embedded_graph_data():
    dangerous = "</script><script>alert(1)</script>"
    graph = Graph(
        nodes={
            dangerous: Node(
                dangerous,
                dangerous,
                dangerous,
                "unsafe<script>.py",
                1,
                1,
                "function",
            )
        },
        metadata={"entry": dangerous},
    )

    document = render_html(graph)

    assert dangerous not in document
    assert "&lt;/script&gt;" in document
    assert "\\u003c/script\\u003e" in document
    assert document.count("<script>") == 1


def test_places_callees_in_layers_from_left_to_right():
    nodes = {
        node_id: Node(node_id, node_id, node_id, "app.py", 1, 1, "function")
        for node_id in ("entry", "first", "second")
    }
    graph = Graph(
        nodes=nodes,
        edges=[Edge("entry", "first", 2), Edge("first", "second", 3)],
        metadata={"entry": "entry"},
    )

    document = render_html(graph)

    assert 'data-node-id="entry" transform="translate(80 80)"' in document
    assert 'data-node-id="first" transform="translate(390 80)"' in document
    assert 'data-node-id="second" transform="translate(700 80)"' in document


def test_orders_nodes_to_avoid_crossing_branches():
    node_ids = ("entry", "left", "right", "left_target", "right_target")
    graph = Graph(
        nodes={
            node_id: Node(node_id, node_id, node_id, "app.py", 1, 1, "function")
            for node_id in node_ids
        },
        edges=[
            Edge("entry", "left", 1),
            Edge("entry", "right", 2),
            Edge("left", "left_target", 20),
            Edge("right", "right_target", 10),
        ],
        metadata={"entry": "entry"},
    )

    positions, _, _ = _layout(graph)

    assert positions["left"][1] < positions["right"][1]
    assert positions["left_target"][1] < positions["right_target"][1]
