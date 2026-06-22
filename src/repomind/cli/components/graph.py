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

    # Build forward and backward adjacency lists
    fwd_adj: dict[str, list[str]] = {}
    rev_adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.source not in fwd_adj:
            fwd_adj[edge.source] = []
        fwd_adj[edge.source].append(edge.target)
        
        if edge.target not in rev_adj:
            rev_adj[edge.target] = []
        rev_adj[edge.target].append(edge.source)

    node_map = {n.qualified_name: n for n in graph.nodes}

    def build_tree(node_name: str, visited: set, current_depth: int, adj_list: dict) -> list[Tree]:
        subtrees = []
        if current_depth < depth and node_name in adj_list:
            for child in adj_list[node_name]:
                if child not in visited:
                    visited.add(child)
                    
                    node = node_map.get(child)
                    if node:
                        style = _get_node_style(node.type)
                        icon = _get_node_icon(node.type)
                        label = Text()
                        label.append(f"{icon} ", style=style)
                        label.append(node.name, style=style)
                    else:
                        label = Text(child, style="white")

                    tree = Tree(label)
                    for st in build_tree(child, visited, current_depth + 1, adj_list):
                        tree.add(st)
                    subtrees.append(tree)
        return subtrees

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

    # Create root tree
    root_node_obj = node_map.get(root_node.qualified_name)
    if root_node_obj:
        style = _get_node_style(root_node_obj.type)
        icon = _get_node_icon(root_node_obj.type)
        root_label = Text()
        root_label.append(f"{icon} ", style=style)
        root_label.append(root_node_obj.name, style=style)
    else:
        root_label = Text(root_node.qualified_name, style="white")
    root_label.append("  (root)", style="bold yellow")
    
    main_tree = Tree(root_label)
    
    # Callers
    callers_label = Text("Callers (upstream)", style="dim italic")
    callers_tree = Tree(callers_label)
    caller_subtrees = build_tree(root_node.qualified_name, {root_node.qualified_name}, 0, rev_adj)
    for st in caller_subtrees:
        callers_tree.add(st)
    if caller_subtrees:
        main_tree.add(callers_tree)
        
    # Callees
    callees_label = Text("Callees (downstream)", style="dim italic")
    callees_tree = Tree(callees_label)
    callee_subtrees = build_tree(root_node.qualified_name, {root_node.qualified_name}, 0, fwd_adj)
    for st in callee_subtrees:
        callees_tree.add(st)
    if callee_subtrees:
        main_tree.add(callees_tree)
        
    console.print(main_tree)

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
