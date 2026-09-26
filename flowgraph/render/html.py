from __future__ import annotations

import html
import json
from collections import deque

from flowgraph.graph.model import Graph


NODE_WIDTH = 230
NODE_HEIGHT = 70
LAYER_GAP = 310
ROW_GAP = 110
PADDING = 80


def render_html(graph: Graph) -> str:
    positions, width, height = _layout(graph)
    edges = "\n".join(
        _render_edge(edge.source, edge.target, positions)
        for edge in sorted(
            graph.edges, key=lambda edge: (edge.source, edge.target, edge.line)
        )
    )
    nodes = "\n".join(
        _render_node(node_id, graph, positions[node_id]) for node_id in sorted(graph.nodes)
    )
    graph_data = json.dumps(graph.to_dict(), separators=(",", ":"))
    graph_data = (
        graph_data.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    title = graph.metadata.get("entry") or graph.metadata.get("from") or "Flowgraph"
    return (
        _PAGE.replace("{{TITLE}}", html.escape(str(title)))
        .replace("{{WIDTH}}", str(width))
        .replace("{{HEIGHT}}", str(height))
        .replace("{{EDGES}}", edges)
        .replace("{{NODES}}", nodes)
        .replace("{{GRAPH_DATA}}", graph_data)
    )


def _layout(graph: Graph) -> tuple[dict[str, tuple[int, int]], int, int]:
    if not graph.nodes:
        return {}, NODE_WIDTH + 2 * PADDING, NODE_HEIGHT + 2 * PADDING

    root = graph.metadata.get("entry") or graph.metadata.get("from")
    if root not in graph.nodes:
        root = min(graph.nodes)

    outgoing: dict[str, list[tuple[int, str]]] = {node_id: [] for node_id in graph.nodes}
    incoming: dict[str, list[tuple[str, int]]] = {
        node_id: [] for node_id in graph.nodes
    }
    incoming_lines: dict[str, list[int]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.source in graph.nodes and edge.target in graph.nodes:
            outgoing[edge.source].append((edge.line, edge.target))
            incoming[edge.target].append((edge.source, edge.line))
            incoming_lines[edge.target].append(edge.line)
    for values in outgoing.values():
        values.sort(key=lambda value: (value[0], value[1]))

    layers = {str(root): 0}
    queue = deque([str(root)])
    while queue:
        source = queue.popleft()
        for _, target in outgoing[source]:
            if target not in layers:
                layers[target] = layers[source] + 1
                queue.append(target)

    next_layer = max(layers.values(), default=-1) + 1
    for node_id in sorted(graph.nodes):
        if node_id not in layers:
            layers[node_id] = next_layer

    grouped: dict[int, list[str]] = {}
    for node_id, layer in layers.items():
        grouped.setdefault(layer, []).append(node_id)
    for node_ids in grouped.values():
        node_ids.sort(
            key=lambda node_id: (
                min(incoming_lines[node_id], default=-1),
                node_id,
            )
        )

    # Keep each child near its callers. Call-site order remains the tie-breaker
    # for siblings with the same parent position.
    row_by_node: dict[str, int] = {}
    for layer in sorted(grouped):
        if layer:
            grouped[layer].sort(
                key=lambda node_id: (
                    _parent_row(node_id, layer, layers, incoming, row_by_node),
                    min(incoming_lines[node_id], default=-1),
                    node_id,
                )
            )
        row_by_node.update(
            {node_id: row for row, node_id in enumerate(grouped[layer])}
        )

    positions = {
        node_id: (PADDING + layer * LAYER_GAP, PADDING + row * ROW_GAP)
        for layer, node_ids in grouped.items()
        for row, node_id in enumerate(node_ids)
    }
    width = PADDING * 2 + NODE_WIDTH + max(grouped) * LAYER_GAP
    height = PADDING * 2 + NODE_HEIGHT + (max(map(len, grouped.values())) - 1) * ROW_GAP
    return positions, width, height


def _parent_row(
    node_id: str,
    layer: int,
    layers: dict[str, int],
    incoming: dict[str, list[tuple[str, int]]],
    row_by_node: dict[str, int],
) -> float:
    rows = [
        row_by_node[source]
        for source, _ in incoming[node_id]
        if layers[source] < layer and source in row_by_node
    ]
    return sum(rows) / len(rows) if rows else float("inf")


def _render_edge(
    source: str, target: str, positions: dict[str, tuple[int, int]]
) -> str:
    if source not in positions or target not in positions:
        return ""
    source_x, source_y = positions[source]
    target_x, target_y = positions[target]
    if source == target:
        start_x = source_x + NODE_WIDTH
        start_y = source_y + NODE_HEIGHT // 2
        path = (
            f"M {start_x} {start_y} C {start_x + 70} {start_y - 80}, "
            f"{start_x + 70} {start_y + 80}, {start_x} {start_y + 8}"
        )
    elif target_x > source_x:
        start_x = source_x + NODE_WIDTH
        start_y = source_y + NODE_HEIGHT // 2
        end_x = target_x
        end_y = target_y + NODE_HEIGHT // 2
        middle = (start_x + end_x) // 2
        path = f"M {start_x} {start_y} C {middle} {start_y}, {middle} {end_y}, {end_x} {end_y}"
    else:
        start_x = source_x + NODE_WIDTH // 2
        start_y = source_y
        end_x = target_x + NODE_WIDTH // 2
        end_y = target_y
        bend_y = min(start_y, end_y) - 38
        path = f"M {start_x} {start_y} C {start_x} {bend_y}, {end_x} {bend_y}, {end_x} {end_y}"
    return (
        f'<path class="edge" data-source="{html.escape(source, quote=True)}" '
        f'data-target="{html.escape(target, quote=True)}" d="{path}" />'
    )


def _render_node(node_id: str, graph: Graph, position: tuple[int, int]) -> str:
    node = graph.nodes[node_id]
    x, y = position
    title = _shorten(f"{node.qualname}()", 30)
    location = _shorten(f"{node.file}:{node.line}", 34)
    escaped_id = html.escape(node_id, quote=True)
    return f'''<g class="node" data-node-id="{escaped_id}" transform="translate({x} {y})" tabindex="0" role="button" aria-label="{escaped_id}">
  <rect width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="10" />
  <text class="node-title" x="16" y="29">{html.escape(title)}</text>
  <text class="node-location" x="16" y="51">{html.escape(location)}</text>
</g>'''


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


_PAGE = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Flowgraph - {{TITLE}}</title>
  <style>
    :root {
      color-scheme: light dark;
      --background: #f4f1ea;
      --surface: #fffdf8;
      --surface-raised: #ffffff;
      --text: #202522;
      --muted: #66706a;
      --border: #d9d4ca;
      --accent: #006b5d;
      --accent-soft: #d6eee8;
      --related: #a35b00;
      --edge: #85918a;
      --shadow: 0 18px 45px rgba(45, 40, 30, .12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--background);
      color: var(--text);
      font: 14px/1.45 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    header {
      display: flex;
      align-items: center;
      gap: 20px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }
    .brand { min-width: max-content; font-weight: 800; letter-spacing: -.04em; font-size: 18px; }
    .brand span { color: var(--accent); }
    .search-wrap { position: relative; flex: 1; max-width: 620px; }
    input, button {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface-raised);
      color: var(--text);
      font: inherit;
    }
    input { width: 100%; padding: 9px 12px; outline: none; }
    input:focus, button:focus-visible, .node:focus-visible rect { outline: 2px solid var(--accent); outline-offset: 2px; }
    #search-status { color: var(--muted); min-width: max-content; font-size: 12px; }
    main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; height: calc(100vh - 67px); }
    .canvas { position: relative; min-width: 0; overflow: hidden; background-image: radial-gradient(var(--border) .7px, transparent .7px); background-size: 20px 20px; }
    #graph { display: block; width: 100%; height: 100%; cursor: grab; user-select: none; touch-action: none; }
    #graph.dragging { cursor: grabbing; }
    .controls {
      position: absolute;
      z-index: 2;
      left: 18px;
      bottom: 18px;
      display: flex;
      gap: 6px;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 11px;
      background: color-mix(in srgb, var(--surface) 90%, transparent);
      box-shadow: var(--shadow);
    }
    button { min-width: 36px; padding: 7px 10px; cursor: pointer; }
    button:hover { border-color: var(--accent); }
    .edge { fill: none; stroke: var(--edge); stroke-width: 1.7; opacity: .28; marker-end: url(#arrow); transition: opacity .15s, stroke .15s; }
    #arrow path { fill: var(--edge); }
    .node { cursor: pointer; transition: opacity .15s; }
    .node rect { fill: var(--surface-raised); stroke: var(--border); stroke-width: 1.5; filter: drop-shadow(0 5px 8px rgba(20, 30, 25, .08)); transition: fill .15s, stroke .15s; }
    .node:hover rect { stroke: var(--accent); }
    .node-title { fill: var(--text); font-size: 14px; font-weight: 700; }
    .node-location { fill: var(--muted); font-size: 11px; }
    .node.selected rect { fill: var(--accent); stroke: var(--accent); }
    .node.selected text { fill: #fff; }
    .node.related rect { fill: var(--accent-soft); stroke: var(--related); }
    .node.dimmed { opacity: .18; }
    .edge.dimmed { opacity: .06; }
    .edge.active { stroke: var(--related); stroke-width: 2.6; opacity: 1; }
    .node.search-match rect { stroke: var(--accent); stroke-width: 3; }
    aside { overflow: auto; padding: 22px; border-left: 1px solid var(--border); background: var(--surface); }
    aside h1 { margin: 0 0 8px; font-size: 17px; overflow-wrap: anywhere; }
    aside h2 { margin: 24px 0 8px; color: var(--muted); font-size: 11px; letter-spacing: .11em; text-transform: uppercase; }
    aside p { margin: 4px 0; }
    aside ul { margin: 0; padding-left: 18px; }
    aside li { margin: 6px 0; overflow-wrap: anywhere; }
    .empty { color: var(--muted); }
    .meta { display: grid; grid-template-columns: auto 1fr; gap: 5px 12px; }
    .meta dt { color: var(--muted); }
    .meta dd { margin: 0; overflow-wrap: anywhere; }
    @media (prefers-color-scheme: dark) {
      :root {
        --background: #101512;
        --surface: #161d19;
        --surface-raised: #202923;
        --text: #edf2ee;
        --muted: #9aa9a0;
        --border: #344139;
        --accent: #55d6bc;
        --accent-soft: #193c34;
        --related: #f2a950;
        --edge: #708078;
        --shadow: 0 18px 45px rgba(0, 0, 0, .35);
      }
      .node.selected text { fill: #10211d; }
    }
    @media (max-width: 760px) {
      header { flex-wrap: wrap; gap: 10px; }
      .search-wrap { order: 3; flex-basis: 100%; max-width: none; }
      main { grid-template-columns: 1fr; grid-template-rows: minmax(55vh, 1fr) auto; height: auto; min-height: calc(100vh - 110px); }
      .canvas { min-height: 55vh; }
      aside { max-height: 38vh; border-top: 1px solid var(--border); border-left: 0; }
    }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; } }
  </style>
</head>
<body>
  <header>
    <div class="brand"><span>flow</span>graph</div>
    <label class="search-wrap">
      <span hidden>Find a function</span>
      <input id="graph-search" type="search" placeholder="Find function or canonical ID..." autocomplete="off">
    </label>
    <span id="search-status" aria-live="polite"></span>
  </header>
  <main>
    <section class="canvas" aria-label="Call graph">
      <svg id="graph" viewBox="0 0 {{WIDTH}} {{HEIGHT}}" role="img" aria-label="Interactive function call graph">
        <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
        <g id="viewport">
{{EDGES}}
{{NODES}}
        </g>
      </svg>
      <nav class="controls" aria-label="Graph controls">
        <button id="zoom-in" type="button" title="Zoom in" aria-label="Zoom in">+</button>
        <button id="zoom-out" type="button" title="Zoom out" aria-label="Zoom out">-</button>
        <button id="fit-graph" type="button">Fit</button>
      </nav>
    </section>
    <aside id="details" aria-live="polite">
      <h1>Explore the call graph</h1>
      <p class="empty">Select a function to inspect its location, callers, callees, and unresolved calls.</p>
    </aside>
  </main>
  <script type="application/json" id="graph-data">{{GRAPH_DATA}}</script>
  <script>
    (() => {
      const data = JSON.parse(document.querySelector('#graph-data').textContent);
      const svg = document.querySelector('#graph');
      const details = document.querySelector('#details');
      const search = document.querySelector('#graph-search');
      const status = document.querySelector('#search-status');
      const nodes = new Map(data.nodes.map(node => [node.id, node]));
      const nodeElements = [...document.querySelectorAll('.node')];
      const edgeElements = [...document.querySelectorAll('.edge')];
      const base = { x: 0, y: 0, width: {{WIDTH}}, height: {{HEIGHT}} };
      let view = { ...base };
      let drag = null;
      let moved = false;
      let selectedId = null;

      function applyView() {
        svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.width} ${view.height}`);
      }

      function zoom(factor) {
        const cx = view.x + view.width / 2;
        const cy = view.y + view.height / 2;
        view.width = Math.max(120, Math.min(base.width * 4, view.width * factor));
        view.height = view.width * (base.height / base.width);
        view.x = cx - view.width / 2;
        view.y = cy - view.height / 2;
        applyView();
      }

      function addText(parent, tag, text, className) {
        const element = document.createElement(tag);
        element.textContent = text;
        if (className) element.className = className;
        parent.append(element);
        return element;
      }

      function addList(title, values) {
        addText(details, 'h2', title);
        if (!values.length) {
          addText(details, 'p', 'None', 'empty');
          return;
        }
        const list = document.createElement('ul');
        values.forEach(value => addText(list, 'li', value));
        details.append(list);
      }

      function highlightNode(id, selectedState) {
        const incoming = data.edges.filter(edge => edge.target === id).map(edge => edge.source);
        const outgoing = data.edges.filter(edge => edge.source === id).map(edge => edge.target);
        const related = new Set([...incoming, ...outgoing]);
        nodeElements.forEach(element => {
          const nodeId = element.dataset.nodeId;
          element.classList.toggle('selected', selectedState && nodeId === id);
          element.classList.toggle('related', related.has(nodeId));
          element.classList.toggle('dimmed', nodeId !== id && !related.has(nodeId));
        });
        edgeElements.forEach(element => {
          const active = element.dataset.source === id || element.dataset.target === id;
          element.classList.toggle('active', active);
          element.classList.toggle('dimmed', !active);
        });
      }

      function resetHighlights() {
        [...nodeElements, ...edgeElements].forEach(element => element.classList.remove('selected', 'related', 'dimmed', 'active'));
      }

      function selectNode(id) {
        const selected = nodes.get(id);
        if (!selected) return;
        selectedId = id;
        highlightNode(id, true);
        const incoming = data.edges.filter(edge => edge.target === id).map(edge => edge.source);
        const outgoing = data.edges.filter(edge => edge.source === id).map(edge => edge.target);

        details.replaceChildren();
        addText(details, 'h1', selected.qualname + '()');
        const meta = document.createElement('dl');
        meta.className = 'meta';
        [['ID', selected.id], ['Kind', selected.kind], ['File', selected.file], ['Lines', `${selected.line}-${selected.end_line}`]].forEach(([term, value]) => {
          addText(meta, 'dt', term);
          addText(meta, 'dd', value);
        });
        details.append(meta);
        addList('Calls', outgoing);
        addList('Called by', incoming);
        const diagnostics = data.diagnostics.filter(item => item.caller === id).map(item => `${item.file}:${item.line} - ${item.expression} - ${item.reason}`);
        addList('Unresolved calls', diagnostics);
      }

      function clearSelection() {
        selectedId = null;
        resetHighlights();
        details.replaceChildren();
        addText(details, 'h1', 'Explore the call graph');
        addText(details, 'p', 'Select a function to inspect its location, callers, callees, and unresolved calls.', 'empty');
      }

      nodeElements.forEach(element => {
        element.addEventListener('click', event => {
          event.stopPropagation();
          selectNode(element.dataset.nodeId);
        });
        element.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectNode(element.dataset.nodeId);
          }
        });
        element.addEventListener('mouseenter', () => highlightNode(element.dataset.nodeId, false));
        element.addEventListener('mouseleave', () => {
          if (selectedId) highlightNode(selectedId, true);
          else resetHighlights();
        });
      });

      search.addEventListener('input', () => {
        const query = search.value.trim().toLowerCase();
        const matches = nodeElements.filter(element => !query || element.dataset.nodeId.toLowerCase().includes(query));
        nodeElements.forEach(element => element.classList.toggle('search-match', Boolean(query) && matches.includes(element)));
        status.textContent = query ? `${matches.length} match${matches.length === 1 ? '' : 'es'}` : `${nodes.size} functions`;
      });
      search.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        const match = nodeElements.find(element => element.classList.contains('search-match'));
        if (match) selectNode(match.dataset.nodeId);
      });

      svg.addEventListener('wheel', event => {
        event.preventDefault();
        const rect = svg.getBoundingClientRect();
        const pointerX = view.x + (event.clientX - rect.left) / rect.width * view.width;
        const pointerY = view.y + (event.clientY - rect.top) / rect.height * view.height;
        const factor = event.deltaY < 0 ? .86 : 1.16;
        const nextWidth = Math.max(120, Math.min(base.width * 4, view.width * factor));
        const nextHeight = nextWidth * (base.height / base.width);
        const ratioX = (pointerX - view.x) / view.width;
        const ratioY = (pointerY - view.y) / view.height;
        view = { x: pointerX - ratioX * nextWidth, y: pointerY - ratioY * nextHeight, width: nextWidth, height: nextHeight };
        applyView();
      }, { passive: false });

      svg.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        drag = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
        moved = false;
        svg.classList.add('dragging');
        svg.setPointerCapture(event.pointerId);
      });
      svg.addEventListener('pointermove', event => {
        if (!drag) return;
        const rect = svg.getBoundingClientRect();
        const dx = (event.clientX - drag.x) * view.width / rect.width;
        const dy = (event.clientY - drag.y) * view.height / rect.height;
        moved ||= Math.abs(dx) + Math.abs(dy) > 2;
        view.x = drag.viewX - dx;
        view.y = drag.viewY - dy;
        applyView();
      });
      svg.addEventListener('pointerup', event => {
        if (drag) svg.releasePointerCapture(event.pointerId);
        drag = null;
        svg.classList.remove('dragging');
      });
      svg.addEventListener('click', event => {
        if (!moved && !event.target.closest('.node')) clearSelection();
      });

      document.querySelector('#zoom-in').addEventListener('click', () => zoom(.8));
      document.querySelector('#zoom-out').addEventListener('click', () => zoom(1.25));
      document.querySelector('#fit-graph').addEventListener('click', () => { view = { ...base }; applyView(); });
      status.textContent = `${nodes.size} functions`;
    })();
  </script>
</body>
</html>
'''
