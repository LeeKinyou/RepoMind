"""MCP Tools registration for RepoMind."""
import json
import os
from mcp.server.fastmcp import FastMCP
from repomind.indexer.file_scanner import IndexService
from repomind.retriever.query_service import QueryService
from repomind.context.context_builder import RCAService
from repomind.models.schemas import IndexOptions, QueryOptions
from repomind.reporter.evidence_report import EvidenceReporter


def _get_index_dir(repo_path: str | None) -> str:
    repo_path = repo_path or os.getcwd()
    return os.path.join(repo_path, ".repomind")


def register_tools(mcp: FastMCP):
    @mcp.tool(name="repomind.index_repository")
    def repomind_index_repository(repo_path: str | None = None, incremental: bool = False) -> str:
        """Index the codebase to build structural database (AST symbols, call graphs, imports)."""
        repo_path = repo_path or os.getcwd()
        index_svc = IndexService(index_dir=_get_index_dir(repo_path))
        opts = IndexOptions(incremental=incremental)
        res = index_svc.index_directory(repo_path, options=opts)
        
        content_text = (
            f"Indexing completed successfully!\n"
            f"- Success: {res.success}\n"
            f"- Total Files: {res.total_files}\n"
            f"- Indexed Files: {res.indexed_files}\n"
            f"- Symbols Found: {res.total_symbols}\n"
            f"- Call Edges: {res.total_calls}\n"
            f"- Index Directory: {res.index_path}\n"
        )
        if res.errors:
            content_text += "- Errors encountered:\n" + "\n".join(f"  * {e}" for e in res.errors)
        return content_text

    @mcp.tool(name="repomind.refresh_index")
    def repomind_refresh_index(repo_path: str | None = None) -> str:
        """Refresh the index only when the workspace has changed since the last snapshot."""
        repo_path = repo_path or os.getcwd()
        index_svc = IndexService(index_dir=_get_index_dir(repo_path))
        res = index_svc.refresh_if_stale(repo_path)
        freshness = index_svc.check_freshness(repo_path)
        if res is None:
            return (
                "Index is already current.\n"
                f"- Index Version: {freshness.index_version}\n"
                f"- Checked Files: {freshness.checked_files}\n"
            )
        return (
            "Index refreshed.\n"
            f"- Success: {res.success}\n"
            f"- Index Version: {index_svc.get_index_version()}\n"
            f"- Indexed Files: {res.indexed_files}\n"
            f"- Symbols Found: {res.total_symbols}\n"
        )

    @mcp.tool(name="repomind.validate_index_freshness")
    def repomind_validate_index_freshness(repo_path: str | None = None) -> str:
        """Validate whether the current workspace still matches the persisted index snapshot."""
        repo_path = repo_path or os.getcwd()
        index_svc = IndexService(index_dir=_get_index_dir(repo_path))
        freshness = index_svc.check_freshness(repo_path)
        lines = [
            f"Freshness: {freshness.status.value}",
            f"Index Version: {freshness.index_version}",
            f"Checked Files: {freshness.checked_files}",
        ]
        if freshness.changed_files:
            lines.append("Changed Files: " + ", ".join(freshness.changed_files))
        if freshness.new_files:
            lines.append("New Files: " + ", ".join(freshness.new_files))
        if freshness.deleted_files:
            lines.append("Deleted Files: " + ", ".join(freshness.deleted_files))
        if freshness.errors:
            lines.append("Errors: " + "; ".join(freshness.errors))
        return "\n".join(lines)

    @mcp.tool(name="repomind.validate_evidence")
    def repomind_validate_evidence(
        report_json: str | None = None,
        file_hashes: dict[str, str] | None = None,
        repo_path: str | None = None,
    ) -> str:
        """Validate report-bound file hashes against the current workspace."""
        repo_path = repo_path or os.getcwd()
        hashes = file_hashes or {}
        if report_json and not hashes:
            try:
                data = json.loads(report_json)
                snapshot = data.get("snapshot") or {}
                hashes = snapshot.get("file_hashes") or {}
            except Exception as e:
                return f"Could not parse report JSON: {e}"

        if not hashes:
            return "No file hashes supplied. Provide report_json or file_hashes."

        index_svc = IndexService(index_dir=_get_index_dir(repo_path))
        freshness = index_svc.validate_file_hashes(repo_path, hashes)
        lines = [
            f"Evidence Freshness: {freshness.status.value}",
            f"Checked Files: {freshness.checked_files}",
        ]
        if freshness.changed_files:
            lines.append("Changed Evidence Files: " + ", ".join(freshness.changed_files))
        if freshness.deleted_files:
            lines.append("Deleted Evidence Files: " + ", ".join(freshness.deleted_files))
        if freshness.errors:
            lines.append("Errors: " + "; ".join(freshness.errors))
        return "\n".join(lines)

    @mcp.tool(name="repomind.changed_files_since")
    def repomind_changed_files_since(repo_path: str | None = None) -> str:
        """Return changed Python files according to the git working tree."""
        repo_path = repo_path or os.getcwd()
        index_svc = IndexService(index_dir=_get_index_dir(repo_path))
        changed = index_svc.changed_files_since(repo_path)
        if not changed:
            return "No changed Python files detected by git status."
        return "\n".join(f"- {path}" for path in changed)

    @mcp.tool(name="repomind.search_symbols")
    def repomind_search_symbols(query: str, max_results: int = 5, repo_path: str | None = None) -> str:
        """Perform code-aware hybrid search (BM25 + SQLite DB) and return AI-generated answer."""
        index_dir = _get_index_dir(repo_path)
        if not os.path.exists(os.path.join(index_dir, "index.db")):
            return f"Index database not found in {index_dir}. Please run 'repomind.index_repository' first."

        query_svc = QueryService(index_dir=index_dir, project_root=repo_path)
        opts = QueryOptions(max_results=max_results)
        res = query_svc.search(query, options=opts)

        content_text = f"### AI Answer:\n{res.answer}\n\n### Matched Symbols:\n"
        for sym in res.symbols:
            content_text += (
                f"- `{sym.qualified_name}` ({sym.type.value})\n"
                f"  File: {sym.file_path} (Lines {sym.start_line}-{sym.end_line})\n"
            )
            if sym.docstring:
                content_text += f"  Docstring: *{sym.docstring.strip()}*\n"
        return content_text

    @mcp.tool(name="repomind.get_symbol_source")
    def repomind_get_symbol_source(qualified_name: str, repo_path: str | None = None) -> str:
        """Get the full source code for a given fully qualified symbol name."""
        index_dir = _get_index_dir(repo_path)
        if not os.path.exists(os.path.join(index_dir, "index.db")):
            return f"Index database not found in {index_dir}."
            
        from repomind.storage.sqlite_store import SQLiteStore
        repo = repo_path or os.getcwd()
        IndexService(index_dir=index_dir).refresh_if_stale(repo)
        sqlite = SQLiteStore(os.path.join(index_dir, "index.db"))
        sym = sqlite.get_symbol_by_qualified_name(qualified_name)
        if not sym:
            return f"Symbol '{qualified_name}' not found."
            
        file_path = sym.get("file_path", "")
        start_line = sym.get("start_line", 0)
        end_line = sym.get("end_line", 0)
        
        try:
            full_path = os.path.join(repo, file_path)
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            snippet = "".join(lines[max(0, start_line - 1):end_line])
            return f"```python\n# {file_path} Lines {start_line}-{end_line}\n{snippet}\n```"
        except Exception as e:
            return f"Error reading file {file_path}: {e}"

    @mcp.tool(name="repomind.expand_symbol_relations")
    def repomind_expand_symbol_relations(qualified_name: str, depth: int = 2, repo_path: str | None = None) -> str:
        """Traverse the static call graph topology starting from a qualified code symbol (BFS)."""
        index_dir = _get_index_dir(repo_path)
        if not os.path.exists(os.path.join(index_dir, "index.db")):
            return f"Index database not found in {index_dir}. Please run 'repomind.index_repository' first."

        query_svc = QueryService(index_dir=index_dir, project_root=repo_path)
        res = query_svc.get_call_graph(qualified_name, depth=depth)

        content_text = f"### Call Graph for `{qualified_name}` (Depth: {depth})\n"
        content_text += "#### Nodes:\n"
        for node in res.nodes:
            content_text += f"- `{node.qualified_name}` ({node.type.value}) in {node.file_path}\n"
        content_text += "\n#### Call Edges:\n"
        for edge in res.edges:
            content_text += f"- `{edge.source}` --({edge.relation_type.value})--> `{edge.target}`\n"
        return content_text

    @mcp.tool(name="repomind.find_failure_evidence")
    def repomind_find_failure_evidence(trace: str, repo_path: str | None = None) -> str:
        """Submit a stack trace / error log to get a detailed deterministic evidence bundle."""
        index_dir = _get_index_dir(repo_path)
        if not os.path.exists(os.path.join(index_dir, "index.db")):
            return f"Index database not found in {index_dir}. Please run 'repomind.index_repository' first."

        rca_svc = RCAService(index_dir=index_dir)
        bundle = rca_svc.collect_trace_evidence(trace)
        
        report = f"### Failure Evidence Summary: {bundle.summary}\n\n"
        if bundle.warnings:
            report += "#### Warnings:\n" + "\n".join(f"- {w}" for w in bundle.warnings) + "\n\n"
            
        report += "#### Evidences:\n"
        for ev in bundle.evidences:
            report += f"- Source: {ev.source}\n  Symbol: `{ev.symbol}`\n  Location: `{ev.file_path}:{ev.start_line}`\n  Reason: {ev.reason}\n"
            if ev.snippet:
                report += f"```python\n{ev.snippet}\n```\n"
        return report

    @mcp.tool(name="repomind.run_diagnostic_agent")
    def repomind_run_diagnostic_agent(trace: str, repo_path: str | None = None) -> str:
        """Submit a stack trace / error log to get a detailed diagnosis evidence report using LLM reasoner."""
        index_dir = _get_index_dir(repo_path)
        if not os.path.exists(os.path.join(index_dir, "index.db")):
            return f"Index database not found in {index_dir}. Please run 'repomind.index_repository' first."

        rca_svc = RCAService(index_dir=index_dir)
        res = rca_svc.analyze_trace(trace)

        # Format using EvidenceReporter
        md_report = EvidenceReporter.generate_markdown_report(
            res, query=trace.strip().split("\n")[-1]
        )
        return md_report
