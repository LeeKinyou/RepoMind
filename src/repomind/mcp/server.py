"""Model Context Protocol (MCP) server implementation for RepoMind."""

from __future__ import annotations

import os
import sys
import json
import traceback
import logging

from repomind.services.index_service import IndexService
from repomind.services.query_service import QueryService
from repomind.services.rca_service import RCAService
from repomind.models.schemas import IndexOptions, QueryOptions
from repomind.reporter.evidence_report import EvidenceReporter

# Configure logging to stderr so it does not interfere with stdout JSON-RPC stream
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("repomind-mcp-server")


class MCPServer:
    """Stdio-based Model Context Protocol (MCP) Server for RepoMind."""

    def __init__(self):
        self.initialized = False

    def start(self) -> None:
        """Start the stdio JSON-RPC processing loop."""
        logger.info("RepoMind MCP server starting...")
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    response = self.handle_message(request)
                    if response is not None:
                        sys.stdout.write(json.dumps(response) + "\n")
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON-RPC line: %s", line)
                    self._send_error(None, -32700, "Parse error")
                except Exception:
                    logger.error("Error processing line: %s", traceback.format_exc())
        except KeyboardInterrupt:
            logger.info("RepoMind MCP server stopped by user.")

    def handle_message(self, request: dict) -> dict | None:
        """Process incoming JSON-RPC request and return response."""
        method = request.get("method")
        msg_id = request.get("id")

        if msg_id is None:
            # Notification, no response needed
            logger.debug("Received notification: %s", method)
            return None

        # 1. Handle initialize handshake
        if method == "initialize":
            self.initialized = True
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "repomind-mcp-server", "version": "0.1.0"},
                },
                "id": msg_id,
            }

        # Handle ping
        if method == "ping":
            return {"jsonrpc": "2.0", "result": {}, "id": msg_id}

        # 2. Block requests if not initialized
        if not self.initialized:
            return self._make_error_response(msg_id, -32002, "Server not initialized")

        # 3. Handle tools/list
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "result": {"tools": self.get_tools_definition()},
                "id": msg_id,
            }

        # 4. Handle tools/call
        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return self.call_tool(tool_name, arguments, msg_id)

        # 5. Method not found fallback
        return self._make_error_response(msg_id, -32601, f"Method not found: {method}")

    def call_tool(self, tool_name: str, arguments: dict, msg_id: int) -> dict:
        """Route to appropriate service and execute the requested tool."""
        logger.info("Calling tool %s with arguments %s", tool_name, arguments)
        try:
            repo_path = arguments.get("repo_path") or os.getcwd()
            index_dir = os.path.join(repo_path, ".repomind")

            if tool_name in ("repomind.index_repo", "repomind_index_repo"):
                incremental = arguments.get("incremental", False)
                index_svc = IndexService(index_dir=index_dir)
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
                    content_text += "- Errors encountered:\n" + "\n".join(
                        f"  * {e}" for e in res.errors
                    )
                return self._make_success_response(msg_id, content_text)

            elif tool_name in ("repomind.search_code", "repomind_search_code"):
                query = arguments.get("query")
                max_results = arguments.get("max_results", 5)

                if not os.path.exists(os.path.join(index_dir, "index.db")):
                    return self._make_success_response(
                        msg_id,
                        f"Index database not found in {index_dir}. Please run 'repomind.index_repo' first.",
                    )

                query_svc = QueryService(index_dir=index_dir)
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
                return self._make_success_response(msg_id, content_text)

            elif tool_name in (
                "repomind.expand_call_chain",
                "repomind_expand_call_chain",
            ):
                qualified_name = arguments.get("qualified_name")
                depth = arguments.get("depth", 2)

                if not os.path.exists(os.path.join(index_dir, "index.db")):
                    return self._make_success_response(
                        msg_id,
                        f"Index database not found in {index_dir}. Please run 'repomind.index_repo' first.",
                    )

                query_svc2 = QueryService(index_dir=index_dir)
                res = query_svc2.get_call_graph(qualified_name, depth=depth)

                content_text = (
                    f"### Call Graph for `{qualified_name}` (Depth: {depth})\n"
                )
                content_text += "#### Nodes:\n"
                for node in res.nodes:
                    content_text += f"- `{node.qualified_name}` ({node.type.value}) in {node.file_path}\n"
                content_text += "\n#### Call Edges:\n"
                for edge in res.edges:
                    content_text += f"- `{edge.source}` --({edge.relation_type.value})--> `{edge.target}`\n"
                return self._make_success_response(msg_id, content_text)

            elif tool_name in ("repomind.diagnose_issue", "repomind_diagnose_issue"):
                trace = arguments.get("trace")

                if not os.path.exists(os.path.join(index_dir, "index.db")):
                    return self._make_success_response(
                        msg_id,
                        f"Index database not found in {index_dir}. Please run 'repomind.index_repo' first.",
                    )

                rca_svc = RCAService(index_dir=index_dir)
                res = rca_svc.analyze_trace(trace)

                # Format using EvidenceReporter
                md_report = EvidenceReporter.generate_markdown_report(
                    res, query=trace.strip().split("\n")[-1]
                )
                return self._make_success_response(msg_id, md_report)

            else:
                return self._make_error_response(
                    msg_id, -32601, f"Unknown tool: {tool_name}"
                )

        except Exception as e:
            logger.error("Tool execution failed: %s", traceback.format_exc())
            return self._make_error_response(
                msg_id, -32001, f"Internal tool execution error: {e}"
            )

    def get_tools_definition(self) -> list[dict]:
        """Return the standard tools manifest for MCP client registration."""
        return [
            {
                "name": "repomind.index_repo",
                "description": "Index the codebase to build structural database (AST symbols, call graphs, imports).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_path": {
                            "type": "string",
                            "description": "The absolute directory path of the repository to index. Defaults to current directory.",
                        },
                        "incremental": {
                            "type": "boolean",
                            "description": "Incremental mode skips indexing files that haven't changed. Defaults to false.",
                        },
                    },
                },
            },
            {
                "name": "repomind.search_code",
                "description": "Perform code-aware hybrid search (BM25 + SQLite DB) and return AI-generated answer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query about codebase or symbol name.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max matched code results to return. Defaults to 5.",
                        },
                        "repo_path": {
                            "type": "string",
                            "description": "The directory of the codebase to query. Defaults to current directory.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "repomind.expand_call_chain",
                "description": "Traverse the static call graph topology starting from a qualified code symbol (BFS).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "qualified_name": {
                            "type": "string",
                            "description": "Fully qualified symbol name (e.g. 'repomind.core.parser.tree_sitter_parser.Parser').",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "BFS traversal depth limit. Defaults to 2.",
                        },
                        "repo_path": {
                            "type": "string",
                            "description": "The directory of the indexed codebase. Defaults to current directory.",
                        },
                    },
                    "required": ["qualified_name"],
                },
            },
            {
                "name": "repomind.diagnose_issue",
                "description": "Submit a stack trace / error log to get a detailed diagnosis evidence report.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "trace": {
                            "type": "string",
                            "description": "The raw python traceback error trace text.",
                        },
                        "repo_path": {
                            "type": "string",
                            "description": "The directory of the indexed codebase. Defaults to current directory.",
                        },
                    },
                    "required": ["trace"],
                },
            },
        ]

    def _make_success_response(self, msg_id: int, text: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": text}]},
            "id": msg_id,
        }

    def _make_error_response(self, msg_id: int, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": msg_id,
        }

    def _send_error(self, msg_id: int | None, code: int, message: str) -> None:
        err = {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": msg_id}
        sys.stdout.write(json.dumps(err) + "\n")
        sys.stdout.flush()
