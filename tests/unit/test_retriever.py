"""Tests for HybridRetriever — covers C4 (RRF) and M5 (BM25 reset)."""

from __future__ import annotations

from repomind.retriever.hybrid_retriever import (
    BM25Index,
    HybridRetriever,
    RetrievalResult,
)
from repomind.storage.graph_store import GraphStore


class TestBM25Index:
    def test_build_and_search(self):
        idx = BM25Index()
        idx.build(
            [
                {
                    "name": "login",
                    "qualified_name": "auth.login",
                    "docstring": "user login",
                    "signature": "",
                },
                {
                    "name": "logout",
                    "qualified_name": "auth.logout",
                    "docstring": "user logout",
                    "signature": "",
                },
                {
                    "name": "process",
                    "qualified_name": "util.process",
                    "docstring": "data processing",
                    "signature": "",
                },
            ]
        )
        results = idx.search("login")
        assert len(results) >= 1
        # login should be the top result
        top_idx, top_score = results[0]
        assert idx.docs[top_idx]["name"] == "login"

    def test_build_resets_state(self):
        """M5: Rebuilding should reset accumulated state."""
        idx = BM25Index()
        idx.build(
            [{"name": "a", "qualified_name": "a", "docstring": "", "signature": ""}]
        )
        assert idx.n == 1
        idx.build(
            [
                {"name": "b", "qualified_name": "b", "docstring": "", "signature": ""},
                {"name": "c", "qualified_name": "c", "docstring": "", "signature": ""},
            ]
        )
        assert idx.n == 2
        assert len(idx.docs) == 2

    def test_search_no_match(self):
        idx = BM25Index()
        idx.build(
            [{"name": "foo", "qualified_name": "foo", "docstring": "", "signature": ""}]
        )
        results = idx.search("zzzzz")
        assert len(results) == 0


class TestRRFFusion:
    """C4: RRF should use real ranks, not score-based approximation."""

    def test_rrf_multi_source(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        results = [
            RetrievalResult(
                symbol={"qualified_name": "a", "name": "a"}, score=10.0, source="bm25"
            ),
            RetrievalResult(
                symbol={"qualified_name": "a", "name": "a"}, score=0.5, source="graph"
            ),
            RetrievalResult(
                symbol={"qualified_name": "b", "name": "b"}, score=5.0, source="bm25"
            ),
        ]
        fused = retriever._rrf_fuse(results, top_k=2)
        assert len(fused) == 2
        # 'a' appears in 2 sources, 'b' in 1 source -> 'a' should rank higher
        assert fused[0].symbol["qualified_name"] == "a"

    def test_rrf_single_source(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        results = [
            RetrievalResult(
                symbol={"qualified_name": "x", "name": "x"}, score=5.0, source="bm25"
            ),
            RetrievalResult(
                symbol={"qualified_name": "y", "name": "y"}, score=10.0, source="bm25"
            ),
        ]
        fused = retriever._rrf_fuse(results, top_k=2)
        # y has higher score -> rank 1 -> higher RRF
        assert fused[0].symbol["qualified_name"] == "y"


class TestVectorDegradation:
    def test_reports_vector_search_degradation_when_extension_is_unavailable(self):
        class StoreWithoutVectors:
            vector_available = False

        retriever = HybridRetriever(StoreWithoutVectors(), GraphStore())

        assert retriever.degraded_features == ["vector_search"]


def test_traceback_graph_expansion(tmp_path):
    from repomind.storage.sqlite_store import SQLiteStore
    from repomind.storage.graph_store import GraphStore
    from repomind.retriever.hybrid_retriever import HybridRetriever
    from repomind.models.schemas import FileInfo, SymbolInfo
    
    db_path = tmp_path / "test.db"
    store = SQLiteStore(str(db_path))
    graph = GraphStore()
    
    # Setup schema records
    fid = store.upsert_file(FileInfo(path="auth.py", hash="h1", language="python", line_count=20, size_bytes=100))
    sid = store.insert_symbol(SymbolInfo(name="login", qualified_name="auth.login", type="function", file_path="auth.py", start_line=5, end_line=15), fid)
    
    fid2 = store.upsert_file(FileInfo(path="db.py", hash="h2", language="python", line_count=20, size_bytes=100))
    sid2 = store.insert_symbol(SymbolInfo(name="query", qualified_name="db.query", type="function", file_path="db.py", start_line=5, end_line=15), fid2)
    
    # Setup import record from auth.py to db.py
    store.insert_import(fid, module_path="db", imported_name="query")
    
    # Setup call graph calls
    store.insert_call(caller_qname="auth.login", callee_qname="db.query", call_type="call")
    from repomind.models.schemas import SymbolRelation, RelationType
    graph.add_symbol("auth.login", type="function")
    graph.add_symbol("db.query", type="function")
    graph.add_relation(SymbolRelation(source="auth.login", target="db.query", relation_type=RelationType.CALLS))
    
    retriever = HybridRetriever(store, graph)
    
    # Query containing a traceback on auth.login
    query = """
    Traceback (most recent call last):
      File "auth.py", line 10, in login
        db.query("sql")
    AttributeError: missing db
    """
    
    res = retriever.retrieve(query, top_k=5)
    # Should resolve auth.login directly, expand to caller/callee db.query, and import mapping
    qnames = [r.symbol["qualified_name"] for r in res]
    assert "auth.login" in qnames
    assert "db.query" in qnames
    
    # Assert that the new structured traceback sources are present in the fused sources
    sources = [r.source for r in res]
    assert any("trace_direct" in s for s in sources)
    assert any("trace_import" in s or "trace_graph" in s for s in sources)
