"""Visualization service - Mermaid diagram generation."""

from __future__ import annotations

import re
from repomind.storage.graph_store import GraphStore
from repomind.models.schemas import CallGraphResult, SymbolType


class VisualizationService:
    """Generate Mermaid diagrams from call graphs."""

    def __init__(self, graph_store: GraphStore | None = None):
        self.graph = graph_store or GraphStore()

    def call_graph_to_mermaid(
        self, result: CallGraphResult, max_nodes: int = 30
    ) -> str:
        """Convert a CallGraphResult to Mermaid diagram."""
        lines = ["graph TD"]
        seen_nodes = set()
        seen_edges = set()

        for node in result.nodes[:max_nodes]:
            safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", node.qualified_name)
            shape = self._node_shape(node.type)
            lines.append(f"    {safe_id}{shape}")
            seen_nodes.add(node.qualified_name)

        for edge in result.edges:
            if edge.source in seen_nodes and edge.target in seen_nodes:
                src = re.sub(r"[^a-zA-Z0-9_]", "_", edge.source)
                tgt = re.sub(r"[^a-zA-Z0-9_]", "_", edge.target)
                edge_key = (src, tgt)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    lines.append(f"    {src} -->|{edge.relation_type.value}| {tgt}")

        return "\n".join(lines)

    def dependency_tree_to_mermaid(self, symbols: list[dict]) -> str:
        """Generate a dependency tree from symbol list."""
        lines = ["graph LR"]
        for sym in symbols:
            qname = sym.get("qualified_name", "")
            safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", qname)
            name = sym.get("name", "?")
            lines.append(f"    {safe_id}[{name}]")
        return "\n".join(lines)

    def _node_shape(self, sym_type: SymbolType) -> str:
        """Return Mermaid node shape based on symbol type."""
        if sym_type == SymbolType.CLASS:
            return "[Class]"
        elif sym_type == SymbolType.METHOD:
            return "(Method)"
        else:
            return "[Func]"
