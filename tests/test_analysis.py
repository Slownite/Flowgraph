from pathlib import Path

from flowgraph.analysis.python_ast import analyze_repository


FIXTURES = Path(__file__).parent / "fixtures"


def edge_pairs(graph):
    return {(edge.source, edge.target) for edge in graph.edges}


def test_extracts_and_resolves_realistic_pipeline():
    graph = analyze_repository(FIXTURES / "pipeline_repo")

    assert "app.py:main" in graph.nodes
    assert graph.nodes["geometry.py:estimate_pose"].line == 13
    assert ("app.py:main", "app.py:load_config") in edge_pairs(graph)
    assert ("app.py:main", "pipeline.py:run_pipeline") in edge_pairs(graph)
    assert (
        "pipeline.py:run_pipeline",
        "features.py:extract_features",
    ) in edge_pairs(graph)
    assert (
        "geometry.py:estimate_pose",
        "geometry.py:compute_transform",
    ) in edge_pairs(graph)


def test_records_dynamic_call_without_inventing_edge():
    graph = analyze_repository(FIXTURES / "pipeline_repo")

    diagnostic = next(
        item for item in graph.diagnostics if item.caller == "pipeline.py:run_dynamic"
    )
    assert diagnostic.expression == "callback"
    assert not any(edge.source == diagnostic.caller for edge in graph.edges)


def test_resolves_relative_imports_and_obvious_methods():
    graph = analyze_repository(FIXTURES / "package_repo")

    assert ("pkg/main.py:start", "pkg/worker.py:execute") in edge_pairs(graph)
    assert (
        "pkg/worker.py:execute",
        "pkg/worker.py:Runner.run",
    ) in edge_pairs(graph)
    assert (
        "pkg/worker.py:Runner.run",
        "pkg/worker.py:Runner.step",
    ) in edge_pairs(graph)
    assert not any(item.expression == "json.dumps" for item in graph.diagnostics)


def test_does_not_resolve_shadowed_function_name(tmp_path):
    (tmp_path / "app.py").write_text(
        "def target():\n"
        "    return 1\n\n"
        "def by_parameter(target):\n"
        "    return target()\n\n"
        "def by_assignment():\n"
        "    target = lambda: 2\n"
        "    return target()\n",
        encoding="utf-8",
    )

    graph = analyze_repository(tmp_path)

    assert not any(
        edge.source in {"app.py:by_parameter", "app.py:by_assignment"}
        for edge in graph.edges
    )
    assert {item.caller for item in graph.diagnostics} >= {
        "app.py:by_parameter",
        "app.py:by_assignment",
    }


def test_does_not_resolve_conditional_or_late_local_import(tmp_path):
    (tmp_path / "helper.py").write_text("def target():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "def conditional():\n"
        "    if False:\n"
        "        from helper import target\n"
        "    return target()\n\n"
        "def late():\n"
        "    value = target()\n"
        "    from helper import target\n"
        "    return value\n\n"
        "def valid():\n"
        "    from helper import target\n"
        "    return target()\n",
        encoding="utf-8",
    )

    graph = analyze_repository(tmp_path)

    assert ("app.py:valid", "helper.py:target") in edge_pairs(graph)
    assert not any(
        edge.source in {"app.py:conditional", "app.py:late"} for edge in graph.edges
    )
