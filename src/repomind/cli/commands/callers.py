"""Callers command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text
from rich.rule import Rule

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner


@dataclass
class CallersCommand:
    """View callers command."""

    name: str = "/callers"
    aliases: list[str] = field(default_factory=lambda: ["/c"])
    description: str = "View who calls this symbol"

    # Dependencies
    console: Any = None
    project_path: Path = None
    query_service: Any = None

    def execute(self, args: str) -> None:
        """Execute callers command.

        Args:
            args: Symbol name
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /callers <symbol-name>",
                    style="yellow",
                )
            )
            return

        self._do_callers(args)

    def _do_callers(self, name: str) -> None:
        """Display callers.

        Args:
            name: Symbol name
        """
        from repomind.models.schemas import QueryOptions

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(name, QueryOptions(max_results=1))

        if not result.symbols:
            self.console.print(
                Text(
                    f"  Not found: {name}",
                    style="yellow",
                )
            )
            return

        sym = result.symbols[0]
        callers = self.query_service.get_callers(sym.qualified_name)

        # Header
        console = self.console
        console.print()
        header = Text()
        header.append("  callers: ", style="dim")
        header.append(sym.name, style="bold cyan")
        header.append(f"  ({len(callers)})", style="dim")
        console.print(header)
        console.print(Rule(style="dim", characters="─"))

        if not callers:
            console.print(Text("  No callers found.", style="dim"))
            console.print()
            return

        for c in callers:
            line = Text()
            line.append("  ← ", style="dim")
            line.append(c.get("name", "?"), style="white")
            if c.get("type"):
                line.append(f"  ({c['type']})", style="dim")
            console.print(line)
        console.print()


def register_callers_command(console, project_path, query_service):
    cmd = CallersCommand(
        console=console, project_path=project_path, query_service=query_service
    )
    registry.register(cmd)
