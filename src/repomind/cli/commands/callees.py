"""Callees command for RepoMind CLI."""

from pathlib import Path
from dataclasses import dataclass, field

from rich.text import Text
from rich.rule import Rule

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner


@dataclass
class CalleesCommand:
    """View callees command."""

    name: str = "/callees"
    aliases: list[str] = field(default_factory=lambda: ["/cl"])
    description: str = "View what this symbol calls"

    # Dependencies
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """Execute callees command.

        Args:
            args: Symbol name
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /callees <symbol-name>",
                    style="yellow",
                )
            )
            return

        self._do_callees(args)

    def _do_callees(self, name: str) -> None:
        """Show callees.

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
        callees = self.query_service.get_callees(sym.qualified_name)

        # Header
        console = self.console
        console.print()
        header = Text()
        header.append("  callees: ", style="dim")
        header.append(sym.name, style="bold cyan")
        header.append(f"  ({len(callees)})", style="dim")
        console.print(header)
        console.print(Rule(style="dim", characters="─"))

        if not callees:
            console.print(Text("  No callees found.", style="dim"))
            console.print()
            return

        for c in callees:
            line = Text()
            line.append("  → ", style="dim")
            line.append(c.get("name", "?"), style="white")
            if c.get("type"):
                line.append(f"  ({c['type']})", style="dim")
            console.print(line)
        console.print()


def register_callees_command(console, project_path, query_service):
    cmd = CalleesCommand(
        console=console, project_path=project_path, query_service=query_service
    )
    registry.register(cmd)
