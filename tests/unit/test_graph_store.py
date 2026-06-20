"""Tests for GraphStore — covers C1 (persistence) and C6 (pickle safety)."""
from __future__ import annotations

import pytest
from repomind.storage.graph_store import GraphStore
from repomind.models.schemas import SymbolRelation, RelationType


class TestGraphStoreBasics:
    def test_empty_graph(self, graph_store):
        assert graph_store.node_count == 0
        assert graph_store.edge_count == 0

    def test_add_symbol(self, graph_store):
        graph_store.add_symbol("pkg.module.func", type="function")
        assert graph_store.node_count == 1

    def test_add_relation(self, graph_store):
        graph_store.add_symbol("a.func1")
        graph_store.add_symbol("a.func2")
        rel = SymbolRelation(source="a.func1", target="a.func2",
                             relation_type=RelationType.CALLS)
        graph_store.add_relation(rel)
        assert graph_store.edge_count == 1


class TestBFSExpand:
    def test_single_node(self, graph_store):
        graph_store.add_symbol("a.func")
        result = graph_store.bfs_expand("a.func", hops=2)
        assert "a.func" in result

    def test_two_hop(self, graph_store):
        graph_store.add_symbol("a")
        graph_store.add_symbol("b")
        graph_store.add_symbol("c")
        graph_store.add_relation(SymbolRelation(source="a", target="b",
                                                relation_type=RelationType.CALLS))
        graph_store.add_relation(SymbolRelation(source="b", target="c",
                                                relation_type=RelationType.CALLS))
        result = graph_store.bfs_expand("a", hops=2)
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_hops_limit(self, graph_store):
        graph_store.add_symbol("a")
        graph_store.add_symbol("b")
        graph_store.add_symbol("c")
        graph_store.add_relation(SymbolRelation(source="a", target="b",
                                                relation_type=RelationType.CALLS))
        graph_store.add_relation(SymbolRelation(source="b", target="c",
                                                relation_type=RelationType.CALLS))
        result = graph_store.bfs_expand("a", hops=1)
        assert "a" in result
        assert "b" in result
        assert "c" not in result


class TestSubgraph:
    def test_get_subgraph(self, graph_store):
        graph_store.add_symbol("a.func", type="function", file_path="a.py")
        graph_store.add_symbol("b.func", type="function", file_path="b.py")
        graph_store.add_relation(SymbolRelation(source="a.func", target="b.func",
                                                relation_type=RelationType.CALLS))
        result = graph_store.get_subgraph({"a.func", "b.func"})
        assert len(result.nodes) == 2
        assert len(result.edges) == 1


class TestPageRank:
    def test_pagerank_empty(self, graph_store):
        assert graph_store.pagerank() == []

    def test_pagerank_with_graph(self, graph_store):
        try:
            import scipy  # noqa: F401
        except ImportError:
            pytest.skip("scipy not installed for PageRank")
        graph_store.add_symbol("a")
        graph_store.add_symbol("b")
        graph_store.add_relation(SymbolRelation(source="a", target="b",
                                                relation_type=RelationType.CALLS))
        result = graph_store.pagerank(top_n=2)
        assert len(result) == 2


class TestPersistence:
    """C1/C6: GraphStore save/load with HMAC verification."""

    def test_save_and_load(self, graph_store, tmp_dir):
        graph_store.add_symbol("a.func")
        graph_store.add_relation(SymbolRelation(source="a.func", target="a.func",
                                                relation_type=RelationType.CALLS))

        path = str(tmp_dir / "test_graph.json")
        graph_store.save(path)

        new_store = GraphStore()
        new_store.load(path)
        assert new_store.node_count == 1
        assert new_store.edge_count == 1

    def test_load_tampered_file_raises(self, graph_store, tmp_dir):
        """C6: Tampered pickle should be rejected."""
        graph_store.add_symbol("a.func")
        path = str(tmp_dir / "test_graph.json")
        graph_store.save(path)

        # Tamper with the file
        with open(path, "rb") as f:
            content = f.read()
        with open(path, "wb") as f:
            f.write(content[:-5] + b"XXXXX")

        new_store = GraphStore()
        with pytest.raises(ValueError, match="signature mismatch"):
            new_store.load(path)

    def test_clear(self, graph_store):
        graph_store.add_symbol("a.func")
        graph_store.clear()
        assert graph_store.node_count == 0


class TestShortestPath:
    def test_path_exists(self, graph_store):
        graph_store.add_symbol("a")
        graph_store.add_symbol("b")
        graph_store.add_symbol("c")
        graph_store.add_relation(SymbolRelation(source="a", target="b",
                                                relation_type=RelationType.CALLS))
        graph_store.add_relation(SymbolRelation(source="b", target="c",
                                                relation_type=RelationType.CALLS))
        path = graph_store.shortest_path("a", "c")
        assert path == ["a", "b", "c"]

    def test_no_path(self, graph_store):
        graph_store.add_symbol("a")
        graph_store.add_symbol("b")
        assert graph_store.shortest_path("a", "b") is None
