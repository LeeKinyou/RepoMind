"""RCA (Root Cause Analysis) component for RepoMind CLI."""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich import box

from repomind.models.schemas import RCAResult


def show_rca_result(console: Console, result: RCAResult) -> None:
    """显示根因分析结果。

    Args:
        console: Rich 控制台实例
        result: RCA 结果
    """
    # 标题和错误信息
    header = Text()
    header.append("[ERROR] ", style="bold red")
    header.append(result.root_cause, style="bold red")

    # 置信度
    conf_style = "bold green" if result.confidence >= 0.7 else "bold yellow" if result.confidence >= 0.4 else "bold red"
    conf_text = Text()
    conf_text.append("Confidence: ", style="dim")
    conf_text.append(f"{result.confidence:.0%}", style=conf_style)

    # 位置信息
    location_text = Text()
    if result.evidence:
        location_text.append("Location: ", style="dim")
        location_text.append(result.evidence[0], style="cyan")

    # 主内容
    content_parts = []

    # 错误信息面板
    error_info = Text()
    error_info.append(header)
    error_info.append("\n\n")
    if location_text:
        error_info.append(location_text)
        error_info.append("\n")
    error_info.append(conf_text)
    content_parts.append(error_info)

    # 调用链
    if result.call_chain:
        chain_text = Text()
        chain_text.append("\nCall Chain\n", style="bold")
        chain_text.append("─" * 60 + "\n", style="dim")

        for i, frame in enumerate(result.call_chain):
            is_last = i == len(result.call_chain) - 1
            prefix = "  [X] " if is_last else "  -> "
            style = "bold red" if is_last else "dim"

            chain_text.append(prefix, style=style)
            chain_text.append(frame + "\n", style=style)

        content_parts.append(chain_text)

    # 分析说明
    if result.explanation:
        explain_text = Text()
        explain_text.append("\nAnalysis\n", style="bold")
        explain_text.append("─" * 60 + "\n", style="dim")
        explain_text.append(result.explanation, style="white")
        content_parts.append(explain_text)

    # 受影响的符号
    if result.affected_symbols:
        symbols_text = Text()
        symbols_text.append("\nAffected Symbols\n", style="bold")
        symbols_text.append("─" * 60 + "\n", style="dim")

        for sym in result.affected_symbols[:10]:
            symbols_text.append(f"  * {sym.name}", style="cyan")
            symbols_text.append(f" ({sym.type.value})", style="dim")
            symbols_text.append(f" at {sym.file_path}:{sym.start_line}\n", style="dim cyan")

        content_parts.append(symbols_text)

    # 修复建议
    if result.suggested_fix:
        fix_text = Text()
        fix_text.append("\nSuggested Fix\n", style="bold")
        fix_text.append("─" * 60 + "\n", style="dim")
        fix_text.append(result.suggested_fix, style="green")
        content_parts.append(fix_text)

    # 组合内容
    from rich.console import Group
    content = Group(*content_parts)

    console.print(Panel(
        content,
        title="[bold red]Root Cause Analysis[/]",
        border_style="red",
        padding=(1, 2),
    ))


def show_rca_trace_input(console: Console) -> None:
    """显示 RCA trace 输入提示。

    Args:
        console: Rich 控制台实例
    """
    console.print(Panel(
        "[yellow]Paste Stack Trace (press Enter twice to finish):[/]",
        title="[bold yellow]Root Cause Analysis[/]",
        border_style="yellow",
    ))
