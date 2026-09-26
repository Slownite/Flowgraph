from pathlib import Path

from flowgraph.analysis.python_ast import analyze_repository
from flowgraph.graph.model import Edge, Graph, Node
from flowgraph.graph.traversal import connecting_graph, reachable_graph, without_excluded


FIXTURE = Path(__file__).parent / "fixtures" / "pipeline_repo"


def test_reachable_graph_honors_depth():
    graph = analyze_repository(FIXTURE)

    result = reachable_graph(graph, "app.py:main", depth=1)

    assert set(result.nodes) == {
        "app.py:main",
        "app.py:load_config",
        "pipeline.py:run_pipeline",
    }


def test_exclusion_removes_node_and_blocks_traversal():
    graph = analyze_repository(FIXTURE)
    filtered = without_excluded(graph, ["features.py:*"])

    result = reachable_graph(filtered, "app.py:main", depth=10)

    assert not any(node_id.startswith("features.py:") for node_id in result.nodes)
    assert "geometry.py:estimate_pose" in result.nodes


def test_connecting_graph_keeps_all_branches_and_merge():
    nodes = {
        name: Node(name, name, name, "fixture.py", 1, 1, "function")
        for name in ("start", "left", "right", "merge", "unrelated")
    }
    graph = Graph(
        nodes=nodes,
        edges=[
            Edge("start", "left", 1),
            Edge("start", "right", 1),
            Edge("left", "merge", 1),
            Edge("right", "merge", 1),
            Edge("start", "unrelated", 1),
        ],
    )

    result = connecting_graph(graph, "start", "merge")

    assert set(result.nodes) == {"start", "left", "right", "merge"}


def test_reachable_depth_zero_contains_only_entry():
    graph = analyze_repository(FIXTURE)

    result = reachable_graph(graph, "app.py:main", depth=0)

    assert set(result.nodes) == {"app.py:main"}
