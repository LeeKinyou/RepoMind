"""Callees command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner


@dataclass
class CalleesCommand:
    """View callees command。"""

    name: str = "/callees"
    aliases: list[str] = field(default_factory=lambda: ["/cl"])
    description: str = "View what this symbol calls"

    # 依赖注入
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """Execute callees command。

        Args:
            args: Symbol name
        """
        if not args:
            self.console.print("[yellow]请提供Symbol name[/]")
            return

        self._do_callees(args)

    def _do_callees(self, name: str) -> None:
        """Show callees。"""
        from repomind.models.schemas import QueryOptions
        from rich.panel import Panel
        from rich.text import Text

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(name, QueryOptions(max_results=1))

        if not result.symbols:
            self.console.print(f"[yellow]Not found: {name}[/]")
            return

        sym = result.symbols[0]
        callees = self.query_service.get_callees(sym.qualified_name)

        if not callees:
            self.console.print(f"[dim]{sym.name} does not call any symbols[/]")
            return

        # 构建结果
        text = Text()
        text.append(f"📦 {sym.name}", style="bold cyan")
        text.append(f" calls ({len(callees)})\n\n", style="white")

        for c in callees:
            text.append("  → ", style="dim")
            text.append(c.get("name", "?"), style="bold white")
            if c.get("type"):
                text.append(f" ({c['type']})", style="dim")
            text.append("\n")

        self.console.print(Panel(
            text,
            title="[bold cyan]📤 Callees[/]",
            border_style="cyan",
        ))


# 注册命令
def register_callees_command(console, project_path, query_service):
    cmd = CalleesCommand(console=console, project_path=project_path, query_service=query_service)
    registry.register(cmd)
