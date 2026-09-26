import json
from pathlib import Path

from flowgraph.cli import run


FIXTURE = Path(__file__).parent / "fixtures" / "pipeline_repo"


def test_cli_writes_reachable_json_mermaid_and_html(tmp_path, capsys):
    result = run(
        [
            str(FIXTURE),
            "--entry",
            "app.py:main",
            "--depth",
            "2",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    document = json.loads((tmp_path / "graph.json").read_text())
    assert document["schema_version"] == 1
    assert {node["id"] for node in document["nodes"]} >= {
        "app.py:main",
        "pipeline.py:run_pipeline",
        "pipeline.py:preprocess",
    }
    assert (tmp_path / "graph.mmd").read_text().startswith("flowchart TD\n")
    html = (tmp_path / "graph.html").read_text()
    assert html.startswith("<!doctype html>\n")
    output = capsys.readouterr().out
    assert f"Wrote {tmp_path / 'graph.html'}" in output


def test_path_cli_accepts_unique_short_names(tmp_path):
    result = run(
        [
            "path",
            str(FIXTURE),
            "--from",
            "main",
            "--to",
            "estimate_pose",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    document = json.loads((tmp_path / "graph.json").read_text())
    ids = {node["id"] for node in document["nodes"]}
    assert ids == {
        "app.py:main",
        "pipeline.py:run_pipeline",
        "geometry.py:estimate_pose",
    }


def test_cli_reports_missing_entry(capsys):
    result = run([str(FIXTURE), "--entry", "missing"])

    assert result == 2
    assert "no function matches" in capsys.readouterr().err
