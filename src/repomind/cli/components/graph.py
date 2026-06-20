"""Graph visualization component for RepoMind CLI."""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich import box

from repomind.models.schemas import CallGraphResult, SymbolType


def _get_node_style(sym_type: SymbolType) -> str:
    """获取节点样式。"""
    styles = {
        SymbolType.CLASS: "bold cyan",
        SymbolType.FUNCTION: "bold green",
        SymbolType.METHOD: "bold yellow",
    }
    return styles.get(sym_type, "white")


def _get_node_icon(sym_type: SymbolType) -> str:
    """获取节点图标。"""
    icons = {
        SymbolType.CLASS: "[C]",
        SymbolType.FUNCTION: "[F]",
        SymbolType.METHOD: "[M]",
    }
    return icons.get(sym_type, "[?]")


def show_call_graph(
    console: Console,
    graph: CallGraphResult,
    root_symbol: str,
    depth: int = 2,
) -> None:
    """显示调用图。

    Args:
        console: Rich 控制台实例
        graph: 调用图结果
        root_symbol: 根符号名称
        depth: 图深度
    """
    if not graph.nodes:
        console.print(Panel(
            "[yellow]No call graph found[/]",
            title="[bold yellow]Call Graph[/]",
            border_style="yellow",
        ))
        return

    # 构建邻接表
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.source not in adj:
            adj[edge.source] = []
        adj[edge.source].append(edge.target)

    # 构建节点映射
    node_map = {n.qualified_name: n for n in graph.nodes}

    # 创建树形结构
    def build_tree(node_name: str, visited: set, current_depth: int) -> Tree:
        node = node_map.get(node_name)
        if node:
            style = _get_node_style(node.type)
            icon = _get_node_icon(node.type)
            label = Text()
            label.append(f"{icon} ", style=style)
            label.append(node.name, style=style)
            if node.qualified_name == root_symbol:
                label.append(" <- root", style="bold yellow")
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

    # 找到根节点
    root_node = None
    for n in graph.nodes:
        if n.qualified_name == root_symbol:
            root_node = n
            break

    if not root_node:
        root_node = graph.nodes[0]

    # 构建树
    visited = {root_node.qualified_name}
    tree = build_tree(root_node.qualified_name, visited, 0)

    # 统计信息
    stats_text = Text()
    stats_text.append(f"\nStats: ", style="dim")
    stats_text.append(f"{len(graph.nodes)}", style="bold cyan")
    stats_text.append(f" nodes, ", style="dim")
    stats_text.append(f"{len(graph.edges)}", style="bold cyan")
    stats_text.append(f" edges", style="dim")

    # 显示
    console.print(Panel(
        tree,
        title=f"[bold cyan]Call Graph: {root_symbol} (depth={depth})[/]",
        subtitle=stats_text,
        border_style="cyan",
        padding=(1, 2),
    ))


def show_call_graph_text(
    console: Console,
    graph: CallGraphResult,
    root_symbol: str,
    depth: int = 2,
) -> None:
    """以文本格式显示调用图（用于 Mermaid 导出）。

    Args:
        console: Rich 控制台实例
        graph: 调用图结果
        root_symbol: 根符号名称
        depth: 图深度
    """
    lines = ["graph TD"]

    # 构建节点映射
    node_map = {n.qualified_name: n for n in graph.nodes}

    # 添加节点
    for node in graph.nodes:
        safe_id = node.qualified_name.replace(".", "_").replace("/", "_")
        name = node.name
        if node.qualified_name == root_symbol:
            lines.append(f"    {safe_id}[/{name}/]:::root")
        else:
            style = "class" if node.type == SymbolType.CLASS else "func"
            lines.append(f"    {safe_id}[{name}]:::{style}")

    # 添加边
    seen_edges = set()
    for edge in graph.edges:
        src = edge.source.replace(".", "_").replace("/", "_")
        tgt = edge.target.replace(".", "_").replace("/", "_")
        edge_key = (src, tgt)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            lines.append(f"    {src} -->|{edge.relation_type.value}| {tgt}")

    # 添加样式
    lines.append("")
    lines.append("    classDef root fill:#f9f,stroke:#333,stroke-width:4px")
    lines.append("    classDef class fill:#bbf,stroke:#333")
    lines.append("    classDef func fill:#bfb,stroke:#333")

    mermaid_code = "\n".join(lines)

    # 显示
    from rich.syntax import Syntax
    syntax = Syntax(mermaid_code, "text", theme="monokai")

    console.print(Panel(
        syntax,
        title=f"[bold cyan]🌐 Mermaid 调用图: {root_symbol}[/]",
        border_style="cyan",
        padding=(1, 2),
    ))
