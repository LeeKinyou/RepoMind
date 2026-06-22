# RepoMind Model Context Protocol (MCP) Server

RepoMind exposes a standardized Model Context Protocol (MCP) stdio server interface, enabling external agent workflows (like Claude Desktop, Cursor, or custom agent systems) to query the codebase, traverse call graphs, and diagnose issues.

## Client Integration Configuration

To integrate the RepoMind MCP server into your environment, add the following to your MCP client configuration file (e.g., `claude_desktop_config.json` or Cursor's MCP server configuration):

### Config Example

```json
{
  "mcpServers": {
    "repomind": {
      "command": "uv",
      "args": [
        "run",
        "repomind",
        "mcp"
      ],
      "cwd": "C:/Users/LeeKinyou/RepoMind"
    }
  }
}
```

> [!NOTE]
> Make sure `cwd` points to the absolute directory where you cloned the RepoMind project and configured your `uv` environment.

---

## Exposed Tools

Once registered, the following tools are available to the host LLM agent:

### 1. `repomind.index_repo`
Indexes the codebase folder structures, AST symbols (classes, functions, methods), import hierarchies, and static call relations.

* **Arguments**:
  - `repo_path` (string, optional): Absolute path to the code repository. Defaults to current workspace directory.
  - `incremental` (boolean, optional): Set to `true` to skip unchanged files. Defaults to `false`.

### 2. `repomind.search_code`
Performs natural language semantic search combined with local keyword indexing (BM25 + SQLite DB matching).

* **Arguments**:
  - `query` (string, required): Natural language search query or specific symbol name.
  - `max_results` (integer, optional): Maximum matched symbol count. Defaults to `5`.
  - `repo_path` (string, optional): Directory path to target. Defaults to current workspace.

### 3. `repomind.expand_call_chain`
Traverses the static call graph topology starting from a qualified code symbol using a Breadth-First Search (BFS) algorithm.

* **Arguments**:
  - `qualified_name` (string, required): Qualified module prefix + symbol name (e.g. `repomind.core.parser.tree_sitter_parser.Parser`).
  - `depth` (integer, optional): BFS depth limit. Defaults to `2`.
  - `repo_path` (string, optional): Directory path to target.

### 4. `repomind.diagnose_issue`
Parses traceback stack traces or error logs, matches frames to local codebase coordinates, extracts snippets, and returns a structured Evidence Report.

* **Arguments**:
  - `trace` (string, required): Raw stack trace logs.
  - `repo_path` (string, optional): Directory path to target.
