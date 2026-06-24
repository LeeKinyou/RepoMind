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
