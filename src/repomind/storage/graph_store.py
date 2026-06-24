"""NetworkX in-memory graph storage for RepoMind."""

from __future__ import annotations

import json
import hashlib
import networkx as nx
from collections import deque

from repomind.models.schemas import (
    SymbolRelation,
    RelationType,
    SymbolInfo,
    CallGraphResult,
    safe_symbol_type,
)
from repomind.utils.errors import GraphLoadError


class GraphStore:
    """In-memory graph storage using NetworkX for fast graph algorithms."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_symbol(self, qualified_name: str, **attrs) -> None:
        self.graph.add_node(qualified_name, **attrs)

    def add_relation(self, relation: SymbolRelation) -> None:
        self.graph.add_edge(
            relation.source,
            relation.target,
            relation_type=relation.relation_type.value,
            weight=relation.weight,
            line_number=relation.line_number,
        )

    def bfs_expand(self, start: str, hops: int = 2) -> set[str]:
        """BFS expansion from a start node, returning all reachable nodes within hops."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if node in visited or depth > hops:
                continue
            if node not in self.graph:
                continue
            visited.add(node)
            for neighbor in set(self.graph.predecessors(node)) | set(
                self.graph.successors(node)
            ):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))
        return visited

    def get_subgraph(self, nodes: set[str]) -> CallGraphResult:
        """Extract a subgraph for the given nodes."""
        sub = self.graph.subgraph(nodes)
        symbol_nodes = []
        edges = []
        for node in sub.nodes():
            data = sub.nodes[node]
            symbol_nodes.append(
                SymbolInfo(
                    name=node.split(".")[-1],
                    qualified_name=node,
                    type=safe_symbol_type(data.get("type", "function")),
                    file_path=data.get("file_path", ""),
                    start_line=data.get("start_line", 0),
                    end_line=data.get("end_line", 0),
                )
            )
        for u, v, data in sub.edges(data=True):
            edges.append(
                SymbolRelation(
                    source=u,
                    target=v,
                    relation_type=RelationType(data.get("relation_type", "calls")),
                    weight=data.get("weight", 1.0),
                )
            )
        return CallGraphResult(nodes=symbol_nodes, edges=edges)

    def pagerank(self, top_n: int = 20) -> list[tuple[str, float]]:
        """Compute PageRank and return top N nodes."""
        if not self.graph.nodes:
            return []
        pr = nx.pagerank(self.graph)
        return sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def find_communities(self) -> list[set[str]]:
        """Detect communities using Louvain (on undirected version)."""
        undirected = self.graph.to_undirected()
        try:
            from networkx.algorithms.community import louvain_communities

            return list(louvain_communities(undirected))
        except ImportError:
            from networkx.algorithms.community import greedy_modularity_communities

            return [set(c) for c in greedy_modularity_communities(undirected)]

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        try:
            return nx.shortest_path(self.graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def clear(self) -> None:
        self.graph.clear()

    def save(self, path: str) -> None:
        """Serialize graph to disk with SHA256 checksum using JSON."""
        data = json.dumps(nx.node_link_data(self.graph)).encode("utf-8")
        sig = hashlib.sha256(data).hexdigest()
        with open(path, "wb") as f:
            f.write(sig.encode() + b"\n" + data)

    def load(self, path: str) -> None:
        """Load graph from disk, verifying SHA256 checksum and loading JSON."""
        import os

        if not os.path.exists(path):
            return  # No graph file yet, start with empty graph

        with open(path, "rb") as f:
            sig_line = f.readline().strip()
            data = f.read()

        if not data:
            return  # Empty file

        try:
            expected = hashlib.sha256(data).hexdigest()
            if sig_line.decode() != expected:
                raise GraphLoadError(
                    "Graph file signature mismatch - possible corruption or tampering"
                )
        except (ValueError, UnicodeDecodeError):
            raise GraphLoadError("Invalid graph file format")

        try:
            graph_data = json.loads(data.decode("utf-8"))
            self.graph = nx.node_link_graph(graph_data)
        except UnicodeDecodeError:
            raise GraphLoadError(
                "Graph file is not in JSON format (possibly legacy pickle format). Delete the file and re-index."
            )
        except Exception as e:
            raise GraphLoadError(f"Failed to parse graph JSON: {e}")

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()
