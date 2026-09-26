from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from flowgraph import __version__
from flowgraph.analysis.python_ast import AnalysisError, analyze_repository
from flowgraph.graph.model import Graph, SelectorError, resolve_selector
from flowgraph.graph.traversal import connecting_graph, reachable_graph, without_excluded
from flowgraph.render.html import render_html
from flowgraph.render.mermaid import render_mermaid
from flowgraph.render.text import render_text


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("repo", type=Path, help="Python repository to analyze")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude canonical function IDs matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".flowgraph"),
        help="output directory, relative to the repository by default",
    )


def _graph_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flowgraph",
        description="Show local Python call flow reachable from an entry function.",
    )
    _common_arguments(parser)
    parser.add_argument(
        "--entry", required=True, help="entry ID, e.g. app.py:main"
    )
    parser.add_argument(
        "--depth", type=int, default=5, help="maximum call depth (default: 5)"
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _path_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flowgraph path",
        description="Show all resolved call flow connecting two functions.",
    )
    _common_arguments(parser)
    parser.add_argument("--from", dest="source", required=True, help="source selector")
    parser.add_argument("--to", dest="target", required=True, help="target selector")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    path_mode = bool(arguments and arguments[0] == "path")
    parser = _path_parser() if path_mode else _graph_parser()
    if path_mode:
        arguments.pop(0)
    args = parser.parse_args(arguments)

    try:
        if getattr(args, "depth", 0) < 0:
            raise ValueError("depth must be zero or greater")
        full_graph = analyze_repository(args.repo)
        filtered = without_excluded(full_graph, args.exclude)
        if path_mode:
            source = resolve_selector(filtered, args.source)
            target = resolve_selector(filtered, args.target)
            graph = connecting_graph(filtered, source, target)
        else:
            entry = resolve_selector(filtered, args.entry)
            graph = reachable_graph(filtered, entry, args.depth)
        output_dir = _output_directory(args.repo, args.output_dir)
        _write_outputs(graph, output_dir)
    except (AnalysisError, SelectorError, ValueError, OSError) as error:
        print(f"flowgraph: error: {error}", file=sys.stderr)
        return 2

    print(render_text(graph))
    print(f"Wrote {output_dir / 'graph.json'}")
    print(f"Wrote {output_dir / 'graph.mmd'}")
    print(f"Wrote {output_dir / 'graph.html'}")
    return 0


def _output_directory(repo: Path, output_dir: Path) -> Path:
    if output_dir.is_absolute():
        return output_dir
    return repo.resolve() / output_dir


def _write_outputs(graph: Graph, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "graph.json").write_text(
        json.dumps(graph.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "graph.mmd").write_text(render_mermaid(graph), encoding="utf-8")
    (output_dir / "graph.html").write_text(render_html(graph), encoding="utf-8")


def main() -> None:
    raise SystemExit(run())
