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
    score_breakdown: dict | None = None
    matched_symbols: list[RetrievalResult] | None = None

    @property
    def file_path(self) -> str:
        return self.symbol.get("file_path", "")

    @property
    def symbol_name(self) -> str | None:
        return self.symbol.get("name")

    @property
    def qualified_name(self) -> str | None:
        return self.symbol.get("qualified_name")

    @property
    def start_line(self) -> int | None:
        return self.symbol.get("start_line")

    @property
    def end_line(self) -> int | None:
        return self.symbol.get("end_line")


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


def tokenize_code_query(text: str) -> set[str]:
    """Tokenize query considering snake_case, camelCase, path segments, and punctuation."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s\./\-]", " ", text)
    words = cleaned.split()
    tokens = set()
    for word in words:
        tokens.add(word.lower())
        if "/" in word or "\\" in word or "." in word:
            segments = re.split(r"[/\.\\\-_]+", word)
            for seg in segments:
                if seg:
                    tokens.add(seg.lower())
        if "_" in word:
            for seg in word.split("_"):
                if seg:
                    tokens.add(seg.lower())
        camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', word)
        for part in camel_parts:
            if part:
                tokens.add(part.lower())
    return {t for t in tokens if len(t) > 1}


def score_token_overlap(query_tokens: set[str], document_tokens: set[str]) -> float:
    """Calculate the overlap ratio between query tokens and document tokens."""
    if not query_tokens or not document_tokens:
        return 0.0
    intersection = query_tokens.intersection(document_tokens)
    return len(intersection) / len(query_tokens)


def normalize_path(path: str) -> str:
    """Normalize Windows/Linux path separators, relative path, lower case."""
    if not path:
        return ""
    p = path.replace("\\", "/").lower()
    while p.startswith("./"):
        p = p[2:]
    return p


def normalize_symbol(symbol: str) -> str:
    """Normalize symbols (remove Class name prefix if Class.method etc.)."""
    if not symbol:
        return ""
    symbol = symbol.lower()
    if "." in symbol:
        return symbol.split(".")[-1]
    return symbol


def aggregate_symbol_results_to_files(symbol_results: list[RetrievalResult], top_k: int = 3) -> list[RetrievalResult]:
    """Aggregate symbol-level results to file-level results.
    
    If multiple symbols match in the same file, the file's score is:
    max_score + 0.1 * sum(other_scores).
    """
    file_map = {}

    for result in symbol_results:
        path = normalize_path(result.file_path)
        if not path:
            continue

        if path not in file_map:
            file_map[path] = {
                "best_result": result,
                "scores": [result.score],
                "matched_symbols": [result]
            }
        else:
            file_map[path]["scores"].append(result.score)
            file_map[path]["matched_symbols"].append(result)
            if result.score > file_map[path]["best_result"].score:
                file_map[path]["best_result"] = result

    aggregated = []
    for path, data in file_map.items():
        best_res = data["best_result"]
        scores = sorted(data["scores"], reverse=True)
        final_score = scores[0]
        if len(scores) > 1:
            final_score += 0.1 * sum(scores[1:])
        
        aggregated.append(
            RetrievalResult(
                symbol=best_res.symbol,
                score=final_score,
                source=best_res.source,
                matched_text=best_res.matched_text,
                score_breakdown=best_res.score_breakdown,
                matched_symbols=data["matched_symbols"]
            )
        )

    ranked = sorted(aggregated, key=lambda r: r.score, reverse=True)
    return ranked[:top_k]


class HybridRetriever:
    """Hybrid retrieval: BM25 + vector search + graph expansion, fused via RRF."""

    def __init__(self, sqlite_store: SQLiteStore, graph_store: GraphStore):
        self.sqlite = sqlite_store
        self.graph = graph_store
        self.bm25 = BM25Index()
        self._built = False
        self.degraded_features = (
            []
            if getattr(sqlite_store, "vector_available", False)
            else ["vector_search"]
        )

    def build_index(self) -> None:
        """Build BM25 index from all symbols in SQLite."""
        symbols = self.sqlite.get_all_symbols()
        self.bm25.build(symbols)
        self._built = True

    def retrieve(
        self, query: str, top_k: int = 10, expand_hops: int = 2, mode: str = "full"
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with BM25, keyword, vector search, graph expansion, and stack trace boosts."""
        if not self._built:
            self.build_index()

        from repomind.context.traceback_parser import is_stack_trace, parse_stack_trace
        from pathlib import Path

        # 1. Fetch BM25 candidates
        bm25_hits = self.bm25.search(query, top_k=top_k * 4)
        bm25_results = []
        for idx, score in bm25_hits:
            if idx < len(self.bm25.docs):
                doc = self.bm25.docs[idx]
                bm25_results.append(
                    RetrievalResult(
                        symbol=doc,
                        score=score,
                        source="bm25",
                        matched_text=f"{doc.get('name', '')} ({doc.get('type', '')})",
                    )
                )

        # 2. Fetch SQLite keyword candidates
        sql_hits = self.sqlite.search_symbols(query, limit=top_k * 4)
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

        # Handle baselines
        if mode == "keyword_only":
            candidates = {}
            for doc in sql_hits:
                qname = doc.get("qualified_name") or doc.get("name")
                if qname:
                    candidates[qname] = doc
            for idx, _ in bm25_hits:
                if idx < len(self.bm25.docs):
                    doc = self.bm25.docs[idx]
                    qname = doc.get("qualified_name") or doc.get("name")
                    if qname and qname not in candidates:
                        candidates[qname] = doc
            results = [
                RetrievalResult(symbol=doc, score=1.0 - (i * 0.01), source="keyword")
                for i, doc in enumerate(candidates.values())
            ]
            return aggregate_symbol_results_to_files(results, top_k)

        if mode == "symbol_only":
            query_tokens = tokenize_code_query(query)
            candidates = []
            
            all_symbols = self.sqlite.get_all_symbols()
            
            for doc in all_symbols:
                name_lower = doc.get("name", "").lower()
                qname_lower = doc.get("qualified_name", "").lower()
                
                score = 0.0
                
                # Direct name match
                if name_lower in query_tokens:
                    score += 10.0
                
                # Qualified name token overlap
                qname_tokens = tokenize_code_query(qname_lower)
                overlap = len(query_tokens.intersection(qname_tokens))
                score += overlap * 2.0
                
                # Boost if the file path is mentioned in the query
                file_path = doc.get("file_path", "")
                if file_path:
                    file_name = Path(file_path).name.lower()
                    if file_name in query_tokens:
                        score += 5.0
                    else:
                        file_stem = Path(file_path).stem.lower()
                        if file_stem in query_tokens:
                            score += 4.0
                
                if score > 0:
                    candidates.append(
                        RetrievalResult(
                            symbol=doc,
                            score=score,
                            source="symbol_only",
                            matched_text=f"symbol match (score: {score})"
                        )
                    )
            
            candidates.sort(key=lambda r: r.score, reverse=True)
            aggregated = aggregate_symbol_results_to_files(candidates, top_k)
            return aggregated

        # 3. Fetch Vector candidates
        vector_hits = []
        vector_results = []
        try:
            from repomind.utils.config import load_config
            import litellm

            config = load_config()
            if config.llm.embedding_model and getattr(
                self.sqlite, "vector_available", False
            ):
                api_key = config.llm.api_key or None
                api_base = config.llm.base_url or None

                resp = litellm.embedding(
                    model=config.llm.embedding_model,
                    input=[query],
                    api_key=api_key,
                    api_base=api_base,
                )
                if resp.data:
                    query_emb = resp.data[0]["embedding"]
                    vector_hits = self.sqlite.search_vectors(query_emb, limit=top_k * 4)
                    for doc in vector_hits:
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
            logging.getLogger(__name__).debug(
                "Vector search skipped: %s", str(e).split("\n")[0]
            )

        # 4. Fetch Graph neighbors
        graph_hits = []
        graph_results = []
        seed_qnames = []
        for doc in sql_hits[:3]:
            if doc.get("qualified_name"):
                seed_qnames.append(doc["qualified_name"])
        for idx, _ in bm25_hits[:3]:
            if idx < len(self.bm25.docs):
                q = self.bm25.docs[idx].get("qualified_name")
                if q:
                    seed_qnames.append(q)

        for qname in set(seed_qnames):
            expanded = self.graph.bfs_expand(qname, hops=expand_hops)
            for eq in expanded:
                sym = self.sqlite.get_symbol_by_qualified_name(eq)
                if sym:
                    graph_hits.append(sym)
                    graph_results.append(
                        RetrievalResult(
                            symbol=sym,
                            score=0.5,
                            source="graph",
                            matched_text=f"graph-expanded: {eq}",
                        )
                    )

        # 5. Fetch Stack Trace direct matches, neighbor graph, and imports
        tb_hits = []
        tb_results = []
        is_query_tb = is_stack_trace(query)
        parsed_tb = parse_stack_trace(query) if is_query_tb else None

        if is_query_tb and parsed_tb:
            expanded_seen = set()
            for frame in parsed_tb.frames:
                if frame.file_path:
                    fname = Path(frame.file_path).name
                    func_name = frame.function_name
                    
                    # 1. Direct Match: Fetch symbol metadata
                    with self.sqlite._read_connect() as conn:
                        rows = conn.execute(
                            """SELECT s.*, f.path AS file_path 
                               FROM symbols s
                               JOIN files f ON s.file_id = f.id
                               WHERE s.name = ? AND (f.path = ? OR f.path LIKE ?)""",
                            (func_name, frame.file_path, f"%{fname}"),
                        ).fetchall()
                        matches = [dict(r) for r in rows]

                    for sym in matches:
                        qname = sym["qualified_name"]
                        if qname not in expanded_seen:
                            expanded_seen.add(qname)
                            tb_hits.append((sym, "trace_direct", 1.2))
                            tb_results.append(
                                RetrievalResult(
                                    symbol=sym,
                                    score=1.2,
                                    source="trace_direct",
                                    matched_text=f"trace-direct: {qname}",
                                )
                            )

                        # 2. Call Graph Neighbors (BFS up to 2 hops)
                        hops = self.graph.bfs_expand(qname, hops=2)
                        for neighbor in hops:
                            if neighbor not in expanded_seen:
                                expanded_seen.add(neighbor)
                                nsym = self.sqlite.get_symbol_by_qualified_name(neighbor)
                                if nsym:
                                    tb_hits.append((nsym, "trace_graph", 0.9))
                                    tb_results.append(
                                        RetrievalResult(
                                            symbol=nsym,
                                            score=0.9,
                                            source="trace_graph",
                                            matched_text=f"trace-graph from {qname}: {neighbor}",
                                        )
                                    )

                        # 3. Import Mapping
                        file_path = sym["file_path"]
                        file_imports = self.sqlite.get_imports_for_file(file_path)
                        for imp in file_imports:
                            module = imp["module_path"]
                            with self.sqlite._read_connect() as conn:
                                rows = conn.execute(
                                    """SELECT s.*, f.path AS file_path 
                                       FROM symbols s
                                       JOIN files f ON s.file_id = f.id
                                       WHERE f.path LIKE ?""",
                                    (f"%{module}.py",),
                                ).fetchall()
                                imported_symbols = [dict(r) for r in rows]
                            for isym in imported_symbols:
                                iqname = isym["qualified_name"]
                                if iqname not in expanded_seen:
                                    expanded_seen.add(iqname)
                                    tb_hits.append((isym, "trace_import", 0.8))
                                    tb_results.append(
                                        RetrievalResult(
                                            symbol=isym,
                                            score=0.8,
                                            source="trace_import",
                                            matched_text=f"trace-import from {file_path}: {iqname}",
                                        )
                                    )

        # RRF Fusion baseline if mode is "hybrid"
        if mode == "hybrid":
            all_results = tb_results + bm25_results + sql_results + vector_results + graph_results
            fused = self._rrf_fuse(all_results, len(all_results))
            return aggregate_symbol_results_to_files(fused, top_k)

        # Deduplicate candidates for Full Reranking
        candidates = {}
        for doc in sql_hits:
            qname = doc.get("qualified_name") or doc.get("name")
            if qname:
                if qname not in candidates:
                    candidates[qname] = (doc, {"keyword"}, 1.0)
                else:
                    candidates[qname][1].add("keyword")

        for idx, score in bm25_hits:
            if idx < len(self.bm25.docs):
                doc = self.bm25.docs[idx]
                qname = doc.get("qualified_name") or doc.get("name")
                if qname:
                    if qname not in candidates:
                        candidates[qname] = (doc, {"bm25"}, score)
                    else:
                        candidates[qname][1].add("bm25")

        for doc in vector_hits:
            qname = doc.get("qualified_name") or doc.get("name")
            if qname:
                dist = doc.get("distance", 1.0)
                sim_score = 1.0 / (1.0 + dist)
                if qname not in candidates:
                    candidates[qname] = (doc, {"vector"}, sim_score)
                else:
                    candidates[qname][1].add("vector")

        for doc in graph_hits:
            qname = doc.get("qualified_name") or doc.get("name")
            if qname:
                if qname not in candidates:
                    candidates[qname] = (doc, {"graph"}, 0.5)
                else:
                    candidates[qname][1].add("graph")

        for doc, tb_source, tb_score in tb_hits:
            qname = doc.get("qualified_name") or doc.get("name")
            if qname:
                if qname not in candidates:
                    candidates[qname] = (doc, {tb_source}, tb_score)
                else:
                    candidates[qname][1].add(tb_source)

        # Rerank Loop
        query_tokens = tokenize_code_query(query)
        reranked_results = []

        for qname, (doc, sources_set, orig_score) in candidates.items():
            semantic_score = 0.0
            keyword_score = 0.0
            path_score = 0.0
            symbol_score = 0.0
            stacktrace_score = 0.0

            # 1. Semantic score
            if "vector" in sources_set:
                semantic_score = orig_score * 10.0

            # 2. Keyword score
            doc_text = f"{doc.get('name', '')} {doc.get('qualified_name', '')} {doc.get('docstring', '') or ''} {doc.get('signature', '') or ''}"
            doc_tokens = tokenize_code_query(doc_text)
            overlap = score_token_overlap(query_tokens, doc_tokens)
            keyword_score = overlap * 10.0
            if "bm25" in sources_set:
                keyword_score += orig_score / 5.0

            # 3. Path score
            file_path = doc.get("file_path", "")
            if file_path:
                file_path_norm = normalize_path(file_path)
                path_tokens = tokenize_code_query(file_path)
                path_overlap = score_token_overlap(query_tokens, path_tokens)
                path_score = path_overlap * 15.0
                for token in query_tokens:
                    if token.endswith(".py") or len(token) > 3:
                        if token in file_path_norm:
                            path_score += 5.0

            # 4. Symbol score
            doc_name = doc.get("name", "").lower()
            if doc_name and doc_name in query_tokens:
                symbol_score += 15.0
            if qname.lower() in query_tokens:
                symbol_score += 25.0

            # 5. Stacktrace score
            if is_query_tb and parsed_tb:
                for frame in parsed_tb.frames:
                    if frame.file_path:
                        frame_file_norm = normalize_path(frame.file_path)
                        file_path_norm = normalize_path(file_path)

                        is_path_match = False
                        if file_path_norm == frame_file_norm:
                            stacktrace_score += 100.0
                            is_path_match = True
                        elif file_path_norm.endswith(frame_file_norm) or frame_file_norm.endswith(file_path_norm):
                            stacktrace_score += 80.0
                            is_path_match = True
                        elif Path(file_path_norm).name == Path(frame_file_norm).name:
                            stacktrace_score += 60.0
                            is_path_match = True

                        if is_path_match:
                            if frame.function_name:
                                frame_func_norm = normalize_symbol(frame.function_name)
                                cand_func_norm = normalize_symbol(doc.get("name", ""))
                                if frame_func_norm == cand_func_norm:
                                    stacktrace_score += 50.0
                            if frame.line_number is not None:
                                start_line = doc.get("start_line", 0)
                                end_line = doc.get("end_line", 0)
                                if start_line <= frame.line_number <= end_line:
                                    stacktrace_score += 40.0

                if parsed_tb.error_message:
                    err_tokens = tokenize_code_query(parsed_tb.error_message)
                    if err_tokens.intersection(doc_tokens):
                        stacktrace_score += 20.0

                if "test" in file_path.lower():
                    has_test_in_trace = any(
                        f.file_path and "test" in f.file_path.lower()
                        for f in parsed_tb.frames
                    )
                    if not has_test_in_trace:
                        stacktrace_score -= 20.0

            final_score = (
                semantic_score
                + keyword_score
                + path_score
                + symbol_score
                + stacktrace_score
            )
            breakdown = {
                "semantic_score": round(semantic_score, 2),
                "keyword_score": round(keyword_score, 2),
                "path_score": round(path_score, 2),
                "symbol_score": round(symbol_score, 2),
                "stacktrace_score": round(stacktrace_score, 2),
                "final_score": round(final_score, 2),
            }

            fused_source = "+".join(sorted(sources_set))
            reranked_results.append(
                RetrievalResult(
                    symbol=doc,
                    score=final_score,
                    source=fused_source,
                    matched_text=f"fused ({fused_source})",
                    score_breakdown=breakdown,
                )
            )

        reranked_results.sort(key=lambda x: x.score, reverse=True)
        return aggregate_symbol_results_to_files(reranked_results, top_k)

    def _rrf_fuse(
        self, results: list[RetrievalResult], top_k: int, k: int = 60
    ) -> list[RetrievalResult]:
        """Reciprocal Rank Fusion across sources."""
        from collections import defaultdict

        by_source: dict[str, list[RetrievalResult]] = defaultdict(list)
        for r in results:
            by_source[r.source].append(r)

        source_rank: dict[str, dict[str, int]] = {}
        for source, items in by_source.items():
            items.sort(key=lambda x: x.score, reverse=True)
            for rank, r in enumerate(items, 1):
                key = r.symbol.get("qualified_name", r.symbol.get("name", ""))
                source_rank.setdefault(source, {})[key] = rank

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
