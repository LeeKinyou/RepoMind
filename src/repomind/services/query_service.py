"""Query service - hybrid retrieval and symbol lookup."""

from __future__ import annotations

from pathlib import Path
import logging
import time
from repomind.utils.errors import QueryError

logger = logging.getLogger(__name__)

from repomind.models.schemas import (
    QueryOptions,
    QueryResult,
    SymbolInfo,
    CallGraphResult,
    safe_symbol_type,
)
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
        from repomind.utils.config import load_config
        from repomind.utils.errors import GraphLoadError
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
                    logger.warning(
                        "Failed to load graph: %s. Starting with empty graph.", e
                    )
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
        """Execute local hybrid retrieval query without LLM calls."""
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
        project_root = Path(self.sqlite.db_path).parent.parent

        for r in results:
            sym_info = self._dict_to_symbol_info(r.symbol)

            # Load code snippet if include_code option is enabled
            if options.include_code:
                try:
                    p = Path(sym_info.file_path)
                    if not p.is_absolute():
                        p = project_root / p
                    if p.exists():
                        lines = p.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                        start_idx = max(0, sym_info.start_line - 1)
                        end_idx = min(len(lines), sym_info.end_line)
                        sym_info.snippet = "\n".join(lines[start_idx:end_idx])
                except Exception:
                    pass

            symbols.append(sym_info)
            sources.append(r.source)

        elapsed = time.time() - start
        answer = f"Found {len(symbols)} results locally for query: '{query}'."

        return QueryResult(
            answer=answer,
            symbols=symbols,
            confidence=max((r.score for r in results), default=0.0),
            sources=list(set(sources)),
            elapsed_seconds=round(elapsed, 3),
        )

    def answer(self, query: str, query_res: QueryResult) -> str:
        """Generate LLM summary answering the query based on retrieved contexts."""
        import litellm
        from repomind.utils.config import load_config
        config = load_config()
        model_name = config.llm.model or "claude-sonnet-4-6"

        context_parts = []
        for sym in query_res.symbols:
            sig = sym.signature or "No signature"
            doc = sym.docstring or "No docstring"
            part = f"- **Symbol**: `{sym.qualified_name}` ({sym.type.value})\n"
            part += f"  **File**: `{sym.file_path}` (Lines {sym.start_line}-{sym.end_line})\n"
            part += f"  **Signature**: `{sig}`\n"
            part += f"  **Docstring**: {doc}\n"
            if sym.snippet:
                part += f"  **Snippet**:\n```python\n{sym.snippet}\n```\n"
            context_parts.append(part)

        symbols_text = (
            "\n".join(context_parts)
            if context_parts
            else "[No relevant symbols found in the index]"
        )

        prompt = (
            f"You are a Repository Intelligence Assistant. Answer the user's question about the codebase "
            f"using the retrieved symbol contexts below. Be precise and professional.\n\n"
            f"User Question:\n{query}\n\n"
            f"Retrieved Code Contexts:\n{symbols_text}\n"
        )

        litellm_args = {}
        if config.llm.api_key:
            litellm_args["api_key"] = config.llm.api_key
        if config.llm.base_url:
            litellm_args["base_url"] = config.llm.base_url

        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                timeout=30,
                **litellm_args,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(
                "LiteLLM completion failed for answering: %s.",
                e,
            )
            return f"Found {len(query_res.symbols)} results for: {query}. (AI answering offline or not configured: {e})"

    def lookup_symbol(self, query: str, limit: int = 1) -> list[SymbolInfo]:
        """Look up symbols locally from database/retriever without calling LLM."""
        try:
            results = self.retriever.retrieve(query, top_k=limit)
            return [self._dict_to_symbol_info(r.symbol) for r in results]
        except Exception:
            return []

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
