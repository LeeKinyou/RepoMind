"""Table components for RepoMind CLI."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich import box

from repomind.models.schemas import SymbolInfo, SymbolType


def _get_type_style(sym_type: SymbolType) -> str:
    """获取符号类型的显示样式。"""
    styles = {
        SymbolType.CLASS: "bold cyan",
        SymbolType.FUNCTION: "bold green",
        SymbolType.METHOD: "bold yellow",
        SymbolType.VARIABLE: "white",
        SymbolType.MODULE: "dim cyan",
        SymbolType.INTERFACE: "bold magenta",
        SymbolType.ENUM: "bold blue",
        SymbolType.PROPERTY: "dim yellow",
    }
    return styles.get(sym_type, "white")


def _get_type_icon(sym_type: SymbolType) -> str:
    """获取符号类型的图标。"""
    icons = {
        SymbolType.CLASS: "[C]",
        SymbolType.FUNCTION: "[F]",
        SymbolType.METHOD: "[M]",
        SymbolType.VARIABLE: "[V]",
        SymbolType.MODULE: "[D]",
        SymbolType.INTERFACE: "[I]",
        SymbolType.ENUM: "[E]",
        SymbolType.PROPERTY: "[P]",
    }
    return icons.get(sym_type, "[?]")


def show_index_stats(console: Console, stats: dict) -> None:
    """显示索引统计信息。

    Args:
        console: Rich 控制台实例
        stats: 统计信息字典
    """
    table = Table(
        box=box.ROUNDED,
        show_header=False,
        padding=(0, 2),
        border_style="cyan",
    )
    table.add_column(style="dim", min_width=12)
    table.add_column(style="bold white")

    items = [
        ("files", "Files"),
        ("symbols", "Symbols"),
        ("classes", "Classes"),
        ("functions", "Functions"),
        ("imports", "Imports"),
        ("calls", "Calls"),
    ]

    for key, label in items:
        if key in stats:
            table.add_row(label, f"{stats[key]:,}")

    console.print(Panel(
        table,
        title="[bold cyan]Index Stats[/]",
        border_style="cyan",
    ))


def show_search_results(
    console: Console,
    query: str,
    results: list[SymbolInfo],
    elapsed: float,
    project_path: str = "",
) -> None:
    """显示搜索结果。

    Args:
        console: Rich 控制台实例
        query: 查询文本
        results: 搜索结果列表
        elapsed: 耗时（秒）
        project_path: 项目路径（用于显示相对路径）
    """
    if not results:
        console.print(Panel(
            f"[yellow]未找到与 [bold]{query}[/] 相关的结果[/]",
            title="[bold yellow]🔍 查询结果[/]",
            border_style="yellow",
        ))
        return

    # 创建结果表格
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        show_edge=False,
    )
    table.add_column(width=4, style="dim")
    table.add_column(min_width=30)
    table.add_column(min_width=40)

    for i, sym in enumerate(results, 1):
        # 符号名称和类型
        type_style = _get_type_style(sym.type)
        type_icon = _get_type_icon(sym.type)
        name_text = Text()
        name_text.append(f"{i:>2}. ", style="dim")
        name_text.append(f"{type_icon} {sym.name}", style=type_style)
        name_text.append(f" ({sym.type.value})", style="dim")

        # 文件位置
        file_text = Text()
        file_path = sym.file_path
        if project_path and file_path.startswith(project_path):
            file_path = file_path[len(project_path):].lstrip("/\\")
        file_text.append(f"@ {file_path}:{sym.start_line}", style="dim cyan")

        # 文档字符串
        doc_text = Text()
        if sym.docstring:
            doc = sym.docstring.split("\n")[0][:60]
            doc_text.append(f"# {doc}", style="dim italic")

        table.add_row(name_text, file_text, doc_text)

    # 显示结果
    header = Text()
    header.append(f"Found ", style="white")
    header.append(f"{len(results)}", style="bold cyan")
    header.append(f" results ", style="white")
    header.append(f"({elapsed:.3f}s)", style="dim cyan")

    console.print(Panel(
        table,
        title=f"[bold cyan]Search: {query}[/]",
        subtitle=header,
        border_style="cyan",
        padding=(1, 2),
    ))

    # 提示信息
    console.print()
    console.print("  [dim]Use /show <name> for details, /graph <name> for call graph[/]")
    console.print()


def show_symbol_detail(
    console: Console,
    symbol: SymbolInfo,
    callers: list[dict] | None = None,
    callees: list[dict] | None = None,
    source_code: str | None = None,
) -> None:
    """显示符号详情。

    Args:
        console: Rich 控制台实例
        symbol: 符号信息
        callers: 调用者列表
        callees: 被调用者列表
        source_code: 源代码
    """
    type_style = _get_type_style(symbol.type)
    type_icon = _get_type_icon(symbol.type)

    # 创建信息表格
    info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    info.add_column(style="dim", min_width=8)
    info.add_column()

    info.add_row("Type", Text(f"{type_icon} {symbol.type.value}", style=type_style))

    if symbol.parent_class:
        info.add_row("Parent", Text(symbol.parent_class, style="cyan"))

    info.add_row("File", Text(f"{symbol.file_path}:{symbol.start_line}-{symbol.end_line}", style="dim cyan"))

    if symbol.signature:
        info.add_row("Signature", Text(symbol.signature, style="green"))

    # 主面板内容
    content_parts = [info]

    # 文档字符串
    if symbol.docstring:
        doc_text = Text()
        doc_text.append("\nDocumentation\n", style="bold")
        doc_text.append("─" * 60 + "\n", style="dim")
        doc_text.append(symbol.docstring, style="white")
        content_parts.append(doc_text)

    # 源代码
    if source_code:
        code_text = Text()
        code_text.append("\nSource Code\n", style="bold")
        code_text.append("─" * 60 + "\n", style="dim")
        content_parts.append(code_text)

        syntax = Syntax(
            source_code,
            "python",
            theme="monokai",
            line_numbers=True,
            start_line=symbol.start_line,
        )
        content_parts.append(syntax)

    # 调用关系
    if callers or callees:
        relations = Text()
        relations.append("\nCall Relations\n", style="bold")
        relations.append("─" * 60 + "\n", style="dim")

        if callers:
            relations.append(f"Called by ({len(callers)}):\n", style="bold")
            for c in callers[:10]:
                relations.append(f"  <- {c.get('name', '?')}\n", style="dim")

        if callees:
            relations.append(f"\nCalls ({len(callees)}):\n", style="bold")
            for c in callees[:10]:
                relations.append(f"  -> {c.get('name', '?')}\n", style="dim")

        content_parts.append(relations)

    # 组合内容
    from rich.console import Group
    content = Group(*content_parts)

    console.print(Panel(
        content,
        title=f"[bold {type_style}]{type_icon} {symbol.name}[/]",
        border_style="cyan",
        padding=(1, 2),
    ))
