"""Self-contained browser visualization for call graphs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from repomind.models.schemas import CallGraphResult


def _graph_payload(
    graph: CallGraphResult,
    root_symbol: str,
    depth: int,
) -> dict:
    return {
        "root": root_symbol,
        "depth": depth,
        "nodes": [
            {
                "id": node.qualified_name,
                "name": node.name,
                "type": node.type.value,
                "file": node.file_path,
                "startLine": node.start_line,
                "endLine": node.end_line,
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "type": edge.relation_type.value,
                "weight": edge.weight,
            }
            for edge in graph.edges
        ],
    }


def render_graph_html(
    graph: CallGraphResult,
    root_symbol: str,
    depth: int,
) -> str:
    """Render a complete directed graph as a standalone interactive HTML page."""
    payload = json.dumps(
        _graph_payload(graph, root_symbol, depth),
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    title = f"RepoMind graph: {root_symbol}"

    template = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: dark;
  --bg: #07111f;
  --panel: rgba(12, 26, 44, .92);
  --line: #5e7896;
  --text: #e8f0fa;
  --muted: #8fa6bd;
  --root: #ffca5c;
  --class: #6ec8ff;
  --method: #9ce38f;
  --function: #c8a4ff;
}
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
body {
  background:
    radial-gradient(circle at 20% 10%, #102b47 0, transparent 34%),
    radial-gradient(circle at 85% 80%, #16233e 0, transparent 38%),
    var(--bg);
  color: var(--text);
  font: 14px/1.4 Inter, ui-sans-serif, system-ui, sans-serif;
}
#graph { width: 100%; height: 100%; cursor: grab; }
#graph:active { cursor: grabbing; }
.edge { stroke: var(--line); stroke-opacity: .55; fill: none; }
.edge.calls { stroke: #70b7ff; }
.edge.imports { stroke: #d5a8ff; stroke-dasharray: 7 5; }
.edge.inherits { stroke: #8de2a1; stroke-width: 2.2; }
.node circle { stroke: #d9e8f7; stroke-width: 1.2; }
.node.root circle { fill: var(--root); stroke: white; stroke-width: 3; }
.node.class circle { fill: var(--class); }
.node.method circle { fill: var(--method); }
.node.function circle { fill: var(--function); }
.node text {
  fill: var(--text);
  font-size: 12px;
  paint-order: stroke;
  stroke: #07111f;
  stroke-width: 4px;
  stroke-linejoin: round;
  pointer-events: none;
}
.node { cursor: pointer; }
.node:hover circle { stroke: white; stroke-width: 3; }
.toolbar, .details {
  position: fixed;
  z-index: 5;
  background: var(--panel);
  border: 1px solid rgba(151, 180, 210, .22);
  box-shadow: 0 16px 40px rgba(0, 0, 0, .28);
  backdrop-filter: blur(10px);
}
.toolbar {
  top: 16px;
  left: 16px;
  right: 16px;
  min-height: 58px;
  border-radius: 12px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 18px;
}
.title { font-weight: 700; max-width: 48vw; overflow: hidden; text-overflow: ellipsis; }
.stats { color: var(--muted); white-space: nowrap; }
.hint { margin-left: auto; color: var(--muted); font-size: 12px; }
.details {
  left: 16px;
  bottom: 16px;
  width: min(560px, calc(100vw - 32px));
  border-radius: 12px;
  padding: 12px 14px;
}
.details strong { display: block; margin-bottom: 4px; word-break: break-all; }
.details span { color: var(--muted); word-break: break-all; }
</style>
</head>
<body>
<div class="toolbar">
  <div class="title" id="title"></div>
  <div class="stats" id="stats"></div>
  <div class="hint">wheel: zoom · drag background: pan · drag node: move</div>
</div>
<svg id="graph" aria-label="Interactive directed call graph">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5"
      markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#91a9c2"></path>
    </marker>
  </defs>
  <g id="viewport">
    <g id="edges"></g>
    <g id="nodes"></g>
  </g>
</svg>
<div class="details" id="details">
  <strong>Select a node</strong>
  <span>Qualified name and source location will appear here.</span>
</div>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("graph-data").textContent);
  const svg = document.getElementById("graph");
  const viewport = document.getElementById("viewport");
  const edgeLayer = document.getElementById("edges");
  const nodeLayer = document.getElementById("nodes");
  const details = document.getElementById("details");
  const width = window.innerWidth;
  const height = window.innerHeight;
  const radius = 9;
  const typeClass = value => ["class", "method", "function"].includes(value)
    ? value : "function";
  const hash = text => {
    let value = 2166136261;
    for (let i = 0; i < text.length; i++) {
      value ^= text.charCodeAt(i);
      value = Math.imul(value, 16777619);
    }
    return value >>> 0;
  };

  document.getElementById("title").textContent = data.root;
  document.getElementById("stats").textContent =
    data.nodes.length + " nodes · " + data.edges.length + " edges · depth " + data.depth;

  const nodes = data.nodes.map((node, index) => {
    const angle = (hash(node.id) % 6283) / 1000;
    const ring = 70 + (index % 13) * 18;
    return {
      ...node,
      x: width / 2 + Math.cos(angle) * ring,
      y: height / 2 + Math.sin(angle) * ring,
      vx: 0,
      vy: 0,
      fixed: false
    };
  });
  const byId = new Map(nodes.map(node => [node.id, node]));
  const edges = data.edges
    .map(edge => ({...edge, sourceNode: byId.get(edge.source), targetNode: byId.get(edge.target)}))
    .filter(edge => edge.sourceNode && edge.targetNode);

  const edgeEls = edges.map(edge => {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "edge " + edge.type);
    line.setAttribute("marker-end", "url(#arrow)");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = edge.source + " --" + edge.type + "--> " + edge.target;
    line.appendChild(title);
    edgeLayer.appendChild(line);
    return line;
  });

  const nodeEls = nodes.map(node => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", "node " + typeClass(node.type) + (node.id === data.root ? " root" : ""));
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("r", node.id === data.root ? 13 : radius);
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", node.id === data.root ? 18 : 14);
    label.setAttribute("y", "4");
    label.textContent = node.name;
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = node.id;
    group.append(circle, label, title);
    group.addEventListener("click", event => {
      event.stopPropagation();
      details.innerHTML = "";
      const strong = document.createElement("strong");
      strong.textContent = node.id;
      const meta = document.createElement("span");
      meta.textContent = node.type + " · " + node.file + ":" + node.startLine + "-" + node.endLine;
      details.append(strong, meta);
    });
    nodeLayer.appendChild(group);
    return group;
  });

  let dragged = null;
  let pan = {x: 0, y: 0};
  let scale = 1;
  let panning = false;
  let lastPointer = null;

  nodeEls.forEach((element, index) => {
    element.addEventListener("pointerdown", event => {
      event.stopPropagation();
      dragged = nodes[index];
      dragged.fixed = true;
      element.setPointerCapture(event.pointerId);
    });
    element.addEventListener("pointermove", event => {
      if (dragged !== nodes[index]) return;
      dragged.x = (event.clientX - pan.x) / scale;
      dragged.y = (event.clientY - pan.y) / scale;
    });
    element.addEventListener("pointerup", event => {
      if (dragged === nodes[index]) dragged = null;
      element.releasePointerCapture(event.pointerId);
    });
  });

  svg.addEventListener("pointerdown", event => {
    panning = true;
    lastPointer = {x: event.clientX, y: event.clientY};
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", event => {
    if (!panning || !lastPointer) return;
    pan.x += event.clientX - lastPointer.x;
    pan.y += event.clientY - lastPointer.y;
    lastPointer = {x: event.clientX, y: event.clientY};
    updateTransform();
  });
  svg.addEventListener("pointerup", event => {
    panning = false;
    lastPointer = null;
    svg.releasePointerCapture(event.pointerId);
  });
  svg.addEventListener("wheel", event => {
    event.preventDefault();
    const oldScale = scale;
    scale = Math.max(.12, Math.min(4, scale * Math.exp(-event.deltaY * .001)));
    pan.x = event.clientX - (event.clientX - pan.x) * scale / oldScale;
    pan.y = event.clientY - (event.clientY - pan.y) * scale / oldScale;
    updateTransform();
  }, {passive: false});
  function updateTransform() {
    viewport.setAttribute("transform", "translate(" + pan.x + " " + pan.y + ") scale(" + scale + ")");
  }

  function simulate(iteration) {
    const alpha = Math.max(.015, 1 - iteration / 520);
    const pairLimit = nodes.length <= 450 ? nodes.length : 90;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let offset = 1; offset < pairLimit; offset++) {
        const j = (i + offset * 37) % nodes.length;
        if (j <= i) continue;
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const distance2 = Math.max(80, dx * dx + dy * dy);
        const force = 1100 / distance2 * alpha;
        const distance = Math.sqrt(distance2);
        dx /= distance;
        dy /= distance;
        a.vx -= dx * force;
        a.vy -= dy * force;
        b.vx += dx * force;
        b.vy += dy * force;
      }
    }
    for (const edge of edges) {
      const a = edge.sourceNode;
      const b = edge.targetNode;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (distance - 115) * .012 * alpha;
      a.vx += dx / distance * force;
      a.vy += dy / distance * force;
      b.vx -= dx / distance * force;
      b.vy -= dy / distance * force;
    }
    const root = byId.get(data.root);
    for (const node of nodes) {
      node.vx += (width / 2 - node.x) * .0007 * alpha;
      node.vy += (height / 2 - node.y) * .0007 * alpha;
      if (node === root) {
        node.vx += (width / 2 - node.x) * .01 * alpha;
        node.vy += (height / 2 - node.y) * .01 * alpha;
      }
      if (!node.fixed) {
        node.vx *= .84;
        node.vy *= .84;
        node.x += node.vx;
        node.y += node.vy;
      }
    }
  }

  function draw() {
    edges.forEach((edge, index) => {
      const line = edgeEls[index];
      line.setAttribute("x1", edge.sourceNode.x);
      line.setAttribute("y1", edge.sourceNode.y);
      line.setAttribute("x2", edge.targetNode.x);
      line.setAttribute("y2", edge.targetNode.y);
    });
    nodes.forEach((node, index) => {
      nodeEls[index].setAttribute("transform", "translate(" + node.x + " " + node.y + ")");
    });
  }

  let iteration = 0;
  function frame() {
    if (iteration < 520 || dragged) {
      simulate(iteration);
      iteration++;
    }
    draw();
    requestAnimationFrame(frame);
  }
  frame();
})();
</script>
</body>
</html>
"""
    return template.replace("__TITLE__", title).replace("__DATA__", payload)


def write_graph_html(
    graph: CallGraphResult,
    root_symbol: str,
    depth: int,
    output_dir: Path,
) -> Path:
    """Write the standalone graph page and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", root_symbol).strip("._")
    output_path = output_dir / f"{safe_name or 'graph'}.html"
    output_path.write_text(
        render_graph_html(graph, root_symbol, depth),
        encoding="utf-8",
    )
    return output_path
