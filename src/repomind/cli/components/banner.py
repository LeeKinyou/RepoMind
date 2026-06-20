"""Banner component for RepoMind CLI."""
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

BANNER_ART = r"""
  ██████╗ ███████╗██████╗  ██████╗ ███╗   ███╗██╗███╗   ██╗██████╗
  ██╔══██╗██╔════╝██╔══██╗██╔═══██╗████╗ ████║██║████╗  ██║██╔══██╗
  ██████╔╝█████╗  ██████╔╝██║   ██║██╔████╔██║██║██╔██╗ ██║██║  ██║
  ██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║
  ██║  ██║███████╗██║     ╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██████╔╝
  ╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝"""


def show_banner(console: Console, project_path: Path, stats: dict | None = None) -> None:
    """显示启动横幅。

    Args:
        console: Rich 控制台实例
        project_path: 项目路径
        stats: 索引统计信息（可选）
    """
    # 创建 ASCII art
    art_text = Text(BANNER_ART, style="bold cyan")

    # 创建信息文本
    info_lines = []
    info_lines.append(Text("Repository Intelligence Platform", style="bold white"))
    info_lines.append(Text(""))
    info_lines.append(Text("  Project: ", style="dim") + Text(str(project_path), style="white"))

    if stats:
        files = stats.get("files", 0)
        symbols = stats.get("symbols", 0)
        classes = stats.get("classes", 0)
        info_lines.append(
            Text("  Index: ", style="dim")
            + Text(f"{files:,}", style="bold cyan")
            + Text(" files | ", style="dim")
            + Text(f"{symbols:,}", style="bold cyan")
            + Text(" symbols | ", style="dim")
            + Text(f"{classes:,}", style="bold cyan")
            + Text(" classes", style="dim")
        )
    else:
        info_lines.append(Text("  Index: ", style="dim") + Text("Not indexed", style="yellow"))

    info_lines.append(Text(""))
    info_lines.append(Text("  Type natural language query, or use / commands", style="dim"))
    info_lines.append(Text("  Type /help for help", style="dim"))

    # 组合内容
    content = art_text.copy()
    for line in info_lines:
        content.append("\n")
        content.append(line)

    # 显示面板
    console.print(Panel(
        content,
        box=box.DOUBLE,
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()
