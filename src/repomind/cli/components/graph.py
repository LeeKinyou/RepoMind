"""Graph visualization component for RepoMind CLI.

Design: clean tree output, no enclosing panel. Uses indentation and
subtle separators instead of heavy box borders.
"""

from rich.console import Console
from rich.text import Text
from rich.tree import Tree
from rich.rule import Rule

from repomind.models.schemas import CallGraphResult, SymbolType


def _get_node_style(sym_type: SymbolType) -> str:
    """Get display style for a node type."""
    styles = {
        SymbolType.CLASS: "bold cyan",
        SymbolType.FUNCTION: "bold green",
        SymbolType.METHOD: "bold yellow",
    }
    return styles.get(sym_type, "white")


def _get_node_icon(sym_type: SymbolType) -> str:
    """Get icon for a node type."""
    icons = {
        SymbolType.CLASS: "C",
        SymbolType.FUNCTION: "F",
        SymbolType.METHOD: "M",
    }
    return icons.get(sym_type, "?")


def show_call_graph(
    console: Console,
    graph: CallGraphResult,
    root_symbol: str,
    depth: int = 2,
) -> None:
    """Display call graph as a clean tree (no enclosing panel).

    Args:
        console: Rich console instance
        graph: Call graph result
        root_symbol: Root symbol name
        depth: Graph depth
    """
    if not graph.nodes:
        console.print()
        line = Text()
        line.append("  No call graph found", style="yellow")
        console.print(line)
        console.print()
        return

    # Build adjacency list
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.source not in adj:
            adj[edge.source] = []
        adj[edge.source].append(edge.target)

    node_map = {n.qualified_name: n for n in graph.nodes}

    def build_tree(node_name: str, visited: set, current_depth: int) -> Tree:
        node = node_map.get(node_name)
        if node:
            style = _get_node_style(node.type)
            icon = _get_node_icon(node.type)
            label = Text()
            label.append(f"{icon} ", style=style)
            label.append(node.name, style=style)
            if node.qualified_name == root_symbol:
                label.append("  (root)", style="bold yellow")
        else:
            label = Text(node_name, style="white")

        tree = Tree(label)

        if current_depth < depth and node_name in adj:
            for child in adj[node_name]:
                if child not in visited:
                    visited.add(child)
                    subtree = build_tree(child, visited, current_depth + 1)
                    tree.add(subtree)

        return tree

    # Find root node
    root_node = None
    for n in graph.nodes:
        if n.qualified_name == root_symbol:
            root_node = n
            break

    if not root_node:
        root_node = graph.nodes[0]

    # Header
    console.print()
    header = Text()
    header.append("  call graph: ", style="dim")
    header.append(root_symbol, style="bold cyan")
    header.append(f"  (depth={depth})", style="dim")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    # Tree
    visited = {root_node.qualified_name}
    tree = build_tree(root_node.qualified_name, visited, 0)
    console.print(tree)

    # Stats footer
    stats = Text()
    stats.append(f"  {len(graph.nodes)}", style="bold cyan")
    stats.append(" nodes, ", style="dim")
    stats.append(f"{len(graph.edges)}", style="bold cyan")
    stats.append(" edges", style="dim")
    console.print(stats)
    console.print()


def show_call_graph_text(
    console: Console,
    graph: CallGraphResult,
    root_symbol: str,
    depth: int = 2,
) -> None:
    """Display call graph as Mermaid text (for export).

    Args:
        console: Rich console instance
        graph: Call graph result
        root_symbol: Root symbol name
        depth: Graph depth
    """
    lines = ["graph TD"]

    for node in graph.nodes:
        safe_id = node.qualified_name.replace(".", "_").replace("/", "_")
        name = node.name
        if node.qualified_name == root_symbol:
            lines.append(f"    {safe_id}[/{name}/]:::root")
        else:
            style = "class" if node.type == SymbolType.CLASS else "func"
            lines.append(f"    {safe_id}[{name}]:::{style}")

    seen_edges = set()
    for edge in graph.edges:
        src = edge.source.replace(".", "_").replace("/", "_")
        tgt = edge.target.replace(".", "_").replace("/", "_")
        edge_key = (src, tgt)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            lines.append(f"    {src} -->|{edge.relation_type.value}| {tgt}")

    lines.append("")
    lines.append("    classDef root fill:#f9f,stroke:#333,stroke-width:4px")
    lines.append("    classDef class fill:#bbf,stroke:#333")
    lines.append("    classDef func fill:#bfb,stroke:#333")

    mermaid_code = "\n".join(lines)

    from rich.syntax import Syntax
    from rich.rule import Rule

    console.print()
    header = Text()
    header.append("  mermaid: ", style="dim")
    header.append(root_symbol, style="bold cyan")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    syntax = Syntax(mermaid_code, "text", theme="monokai", background_color="default")
    console.print(syntax)
    console.print()
