"""Query service - hybrid retrieval and symbol lookup."""
from __future__ import annotations

from pathlib import Path

from repomind.models.schemas import QueryOptions, QueryResult, SymbolInfo, CallGraphResult, safe_symbol_type
from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore
from repomind.core.retrieval.hybrid_retriever import HybridRetriever


class QueryService:
    """Handles hybrid search, symbol info, and call graph queries."""

    def __init__(
        self,
        index_dir: str | None = None,
        sqlite: SQLiteStore | None = None,
        graph: GraphStore | None = None,
        retriever: HybridRetriever | None = None,
    ):
        import logging
        from repomind.utils.config import load_config
        from repomind.utils.errors import GraphLoadError

        logger = logging.getLogger(__name__)
        if index_dir is None:
            index_dir = load_config().index_dir
        self.sqlite = sqlite or SQLiteStore(str(Path(index_dir) / "index.db"))
        self.graph = graph or GraphStore()
        if graph is None:
            graph_path = Path(index_dir) / "graph.json"
            if graph_path.exists():
                try:
                    self.graph.load(str(graph_path))
                except GraphLoadError as e:
                    logger.warning("Failed to load graph: %s. Starting with empty graph.", e)
        self.retriever = retriever or HybridRetriever(self.sqlite, self.graph)

    def _dict_to_symbol_info(self, sym_dict: dict) -> SymbolInfo:
        return SymbolInfo(
            name=sym_dict.get("name", ""),
            qualified_name=sym_dict.get("qualified_name", ""),
            type=safe_symbol_type(sym_dict.get("type", "function")),
            file_path=sym_dict.get("file_path", ""),
            start_line=sym_dict.get("start_line", 0),
            end_line=sym_dict.get("end_line", 0),
            docstring=sym_dict.get("docstring"),
            signature=sym_dict.get("signature"),
        )

    def search(self, query: str, options: QueryOptions | None = None) -> QueryResult:
        """Execute hybrid retrieval query."""
        import time
        import logging
        from repomind.utils.errors import QueryError

        logger = logging.getLogger(__name__)
        start = time.time()
        options = options or QueryOptions()

        try:
            results = self.retriever.retrieve(
                query,
                top_k=options.max_results,
                expand_hops=options.graph_hops,
            )
        except Exception as e:
            logger.error("Search failed for query '%s': %s", query, e)
            raise QueryError(f"Search failed: {e}") from e

        symbols = []
        sources = []
        for r in results:
            symbols.append(self._dict_to_symbol_info(r.symbol))
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
        return self._dict_to_symbol_info(sym)

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
