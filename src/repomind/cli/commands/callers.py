"""Callers command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner


@dataclass
class CallersCommand:
    """View callers command。"""

    name: str = "/callers"
    aliases: list[str] = field(default_factory=lambda: ["/c"])
    description: str = "View who calls this symbol"

    # 依赖注入
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """Execute callers command。

        Args:
            args: 符号名称
        """
        if not args:
            self.console.print("[yellow]请提供符号名称[/]")
            return

        self._do_callers(args)

    def _do_callers(self, name: str) -> None:
        """显示Callers。"""
        from repomind.models.schemas import QueryOptions
        from rich.panel import Panel
        from rich.text import Text

        with show_spinner(self.console, "正在查询..."):
            result = self.query_service.search(name, QueryOptions(max_results=1))

        if not result.symbols:
            self.console.print(f"[yellow]未找到: {name}[/]")
            return

        sym = result.symbols[0]
        callers = self.query_service.get_callers(sym.qualified_name)

        if not callers:
            self.console.print(f"[dim]No callers for: {sym.name}[/]")
            return

        # 构建结果
        text = Text()
        text.append(f"📦 {sym.name}", style="bold cyan")
        text.append(f" called by ({len(callers)})\n\n", style="white")

        for c in callers:
            text.append("  ← ", style="dim")
            text.append(c.get("name", "?"), style="bold white")
            if c.get("type"):
                text.append(f" ({c['type']})", style="dim")
            text.append("\n")

        self.console.print(Panel(
            text,
            title="[bold cyan]📞 Callers[/]",
            border_style="cyan",
        ))


# 注册命令
def register_callers_command(console, project_path, query_service):
    cmd = CallersCommand(console=console, project_path=project_path, query_service=query_service)
    registry.register(cmd)
