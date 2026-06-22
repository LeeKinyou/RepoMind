"""Hybrid retrieval engine combining BM25, vector search, and graph expansion."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore


@dataclass
class RetrievalResult:
    """A single retrieval result with fused score."""

    symbol: dict
    score: float
    source: str  # "bm25", "vector", "graph"
    matched_text: str = ""


class BM25Index:
    """Simple in-memory BM25 index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[dict] = []
        self.doc_freqs: list[Counter] = []
        self.avg_dl: float = 0.0
        self.df: Counter = Counter()
        self.n: int = 0

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text on dots, underscores, and whitespace for code-aware tokenization."""
        return [t for t in re.split(r"[_.\s]+", text.lower()) if t]

    def build(self, documents: list[dict]) -> None:
        """Build index from symbol documents."""
        from collections import defaultdict
        self.doc_freqs = []
        self.df = Counter()
        self.inverted_index = defaultdict(set)
        self.docs = documents
        self.n = len(documents)
        total_len = 0
        for i, doc in enumerate(documents):
            text = f"{doc.get('name', '')} {doc.get('qualified_name', '')} {doc.get('docstring', '') or ''} {doc.get('signature', '') or ''}"
            tokens = self._tokenize(text)
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            total_len += len(tokens)
            for token in set(tokens):
                self.df[token] += 1
                self.inverted_index[token].add(i)
        self.avg_dl = total_len / self.n if self.n > 0 else 1.0

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Search and return (doc_index, score) pairs."""
        query_tokens = self._tokenize(query)
        scores = []
        
        candidate_ids = set()
        for qt in query_tokens:
            if hasattr(self, "inverted_index"):
                candidate_ids |= self.inverted_index.get(qt, set())
        
        if not hasattr(self, "inverted_index"):
            candidate_ids = set(range(len(self.doc_freqs)))
            
        for i in candidate_ids:
            freq = self.doc_freqs[i]
            score = 0.0
            dl = sum(freq.values())
            for qt in query_tokens:
                if qt in freq:
                    tf = freq[qt]
                    df = self.df.get(qt, 0)
                    idf = math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)
                    tf_norm = (tf * (self.k1 + 1)) / (
                        tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                    )
                    score += idf * tf_norm
            scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in scores[:top_k] if s > 0]


class HybridRetriever:
    """Hybrid retrieval: BM25 + vector search + graph expansion, fused via RRF."""

    def __init__(self, sqlite_store: SQLiteStore, graph_store: GraphStore):
        self.sqlite = sqlite_store
        self.graph = graph_store
        self.bm25 = BM25Index()
        self._built = False

    def build_index(self) -> None:
        """Build BM25 index from all symbols in SQLite."""
        symbols = self.sqlite.get_all_symbols()
        self.bm25.build(symbols)
        self._built = True

    def retrieve(
        self, query: str, top_k: int = 10, expand_hops: int = 2
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with BM25 + graph expansion, fused via RRF."""
        if not self._built:
            self.build_index()

        # BM25 results
        bm25_hits = self.bm25.search(query, top_k=top_k * 2)
        bm25_results = []
        for idx, score in bm25_hits:
            doc = self.bm25.docs[idx]
            bm25_results.append(
                RetrievalResult(
                    symbol=doc,
                    score=score,
                    source="bm25",
                    matched_text=f"{doc.get('name', '')} ({doc.get('type', '')})",
                )
            )

        # SQLite keyword search
        sql_hits = self.sqlite.search_symbols(query, limit=top_k * 2)
        sql_results = []
        for doc in sql_hits:
            sql_results.append(
                RetrievalResult(
                    symbol=doc,
                    score=1.0,
                    source="keyword",
                    matched_text=f"{doc.get('name', '')} ({doc.get('type', '')})",
                )
            )

        # Vector search results
        vector_results = []
        try:
            from repomind.utils.config import load_config
            import litellm
            config = load_config()
            if config.llm.embedding_model:
                litellm_args = {}
                if config.llm.api_key:
                    litellm_args["api_key"] = config.llm.api_key
                if config.llm.base_url:
                    litellm_args["base_url"] = config.llm.base_url
                
                resp = litellm.embedding(
                    model=config.llm.embedding_model,
                    input=[query],
                    **litellm_args
                )
                if resp.data:
                    query_emb = resp.data[0]["embedding"]
                    vec_hits = self.sqlite.search_vectors(query_emb, limit=top_k * 2)
                    for doc in vec_hits:
                        dist = doc.get("distance", 1.0)
                        sim_score = 1.0 / (1.0 + dist)
                        vector_results.append(
                            RetrievalResult(
                                symbol=doc,
                                score=sim_score,
                                source="vector",
                                matched_text=f"semantic match (dist: {dist:.2f})",
                            )
                        )
        except Exception as e:
            import logging
            # Log as debug so we don't spam the user if litellm is unconfigured or fails
            logging.getLogger(__name__).debug("Vector search skipped (LLM error): %s", str(e).split('\n')[0])

        # Graph expansion from top BM25 hits
        graph_results = []
        seen_qnames = set()
        for idx, _ in bm25_hits[:5]:
            doc = self.bm25.docs[idx]
            qname = doc.get("qualified_name", "")
            if qname:
                expanded = self.graph.bfs_expand(qname, hops=expand_hops)
                for eq in expanded:
                    if eq not in seen_qnames:
                        seen_qnames.add(eq)
                        sym = self.sqlite.get_symbol_by_qualified_name(eq)
                        if sym:
                            graph_results.append(
                                RetrievalResult(
                                    symbol=sym,
                                    score=0.5,
                                    source="graph",
                                    matched_text=f"graph-expanded: {eq}",
                                )
                            )

        # RRF Fusion
        all_results = bm25_results + sql_results + vector_results + graph_results
        return self._rrf_fuse(all_results, top_k)

    def _rrf_fuse(
        self, results: list[RetrievalResult], top_k: int, k: int = 60
    ) -> list[RetrievalResult]:
        """Reciprocal Rank Fusion across sources."""
        from collections import defaultdict

        # Group by source and rank within each source
        by_source: dict[str, list[RetrievalResult]] = defaultdict(list)
        for r in results:
            by_source[r.source].append(r)

        source_rank: dict[str, dict[str, int]] = {}
        for source, items in by_source.items():
            items.sort(key=lambda x: x.score, reverse=True)
            for rank, r in enumerate(items, 1):
                key = r.symbol.get("qualified_name", r.symbol.get("name", ""))
                source_rank.setdefault(source, {})[key] = rank

        # Group by qualified_name and compute RRF score
        grouped: dict[str, list[RetrievalResult]] = defaultdict(list)
        for r in results:
            key = r.symbol.get("qualified_name", r.symbol.get("name", ""))
            grouped[key].append(r)

        fused = []
        for key, group in grouped.items():
            rrf_score = sum(
                1.0 / (k + source_rank.get(r.source, {}).get(key, len(results)))
                for r in group
            )
            best = max(group, key=lambda x: x.score)
            fused.append(
                RetrievalResult(
                    symbol=best.symbol,
                    score=rrf_score,
                    source="+".join(sorted(set(r.source for r in group))),
                    matched_text=best.matched_text,
                )
            )

        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:top_k]
