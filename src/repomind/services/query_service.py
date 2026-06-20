"""Query service - hybrid retrieval and symbol lookup."""
from __future__ import annotations

from pathlib import Path

from repomind.models.schemas import QueryOptions, QueryResult, SymbolInfo, CallGraphResult, safe_symbol_type
from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore
from repomind.core.retrieval.hybrid_retriever import HybridRetriever


class QueryService:
    """Handles hybrid search, symbol info, and call graph queries."""

    def __init__(self, index_dir: str = ".repomind"):
        self.sqlite = SQLiteStore(f"{index_dir}/index.db")
        self.graph = GraphStore()
        graph_path = Path(index_dir) / "graph.json"
        if graph_path.exists():
            self.graph.load(str(graph_path))
        self.retriever = HybridRetriever(self.sqlite, self.graph)

    def search(self, query: str, options: QueryOptions | None = None) -> QueryResult:
        """Execute hybrid retrieval query."""
        import time
        start = time.time()
        options = options or QueryOptions()

        results = self.retriever.retrieve(
            query,
            top_k=options.max_results,
            expand_hops=options.graph_hops,
        )

        symbols = []
        sources = []
        for r in results:
            sym_dict = r.symbol
            symbols.append(SymbolInfo(
                name=sym_dict.get("name", ""),
                qualified_name=sym_dict.get("qualified_name", ""),
                type=safe_symbol_type(sym_dict.get("type", "function")),
                file_path=sym_dict.get("file_path", ""),
                start_line=sym_dict.get("start_line", 0),
                end_line=sym_dict.get("end_line", 0),
                docstring=sym_dict.get("docstring"),
                signature=sym_dict.get("signature"),
            ))
            sources.append(r.source)

        elapsed = time.time() - start
        return QueryResult(
            answer=f"Found {len(symbols)} results for: {query}",
            symbols=symbols,
            confidence=max((r.score for r in results), default=0.0),
            sources=list(set(sources)),
            elapsed_seconds=round(elapsed, 3),
        )

    def get_symbol_info(self, qualified_name: str) -> SymbolInfo | None:
        """Get detailed symbol info by qualified name."""
        sym = self.sqlite.get_symbol_by_qualified_name(qualified_name)
        if not sym:
            return None
        return SymbolInfo(
            name=sym.get("name", ""),
            qualified_name=sym.get("qualified_name", ""),
            type=safe_symbol_type(sym.get("type", "function")),
            file_path=sym.get("file_path", ""),
            start_line=sym.get("start_line", 0),
            end_line=sym.get("end_line", 0),
            docstring=sym.get("docstring"),
            signature=sym.get("signature"),
        )

    def get_call_graph(self, qualified_name: str, depth: int = 2) -> CallGraphResult:
        """Get call graph for a symbol."""
        expanded = self.graph.bfs_expand(qualified_name, hops=depth)
        return self.graph.get_subgraph(expanded)

    def get_callers(self, qualified_name: str) -> list[dict]:
        """Get all callers of a symbol."""
        return self.sqlite.get_callers(qualified_name)

    def get_callees(self, qualified_name: str) -> list[dict]:
        """Get all callees of a symbol."""
        return self.sqlite.get_callees(qualified_name)
