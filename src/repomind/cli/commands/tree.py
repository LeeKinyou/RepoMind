"""Legacy terminal tree command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.graph import show_call_graph


@dataclass
class TreeCommand:
    """Display the call graph using the legacy terminal tree."""

    name: str = "/tree"
    aliases: list[str] = field(default_factory=lambda: ["/t"])
    description: str = "View call relationships as a terminal tree"

    console: Any = None
    project_path: Path = None
    query_service: Any = None

    def execute(self, args: str) -> None:
        if not args:
            self.console.print(
                Text(
                    "  Usage: /tree <symbol-name> [--depth N | -d N]",
                    style="yellow",
                )
            )
            return

        parts = args.split()
        name = parts[0]
        depth = 2
        for index, part in enumerate(parts):
            if part in ("--depth", "-d") and index + 1 < len(parts):
                try:
                    depth = int(parts[index + 1])
                except ValueError:
                    pass

        with show_spinner(self.console, "Searching..."):
            symbols = self.query_service.lookup_symbol(name, limit=1)

        if not symbols:
            self.console.print(Text(f"  Not found: {name}", style="yellow"))
            return

        symbol = symbols[0]
        graph = self.query_service.get_call_graph(
            symbol.qualified_name,
            depth=depth,
        )
        show_call_graph(
            self.console,
            graph,
            symbol.qualified_name,
            depth,
        )


def register_tree_command(console, project_path, query_service):
    registry.register(
        TreeCommand(
            console=console,
            project_path=project_path,
            query_service=query_service,
        )
    )
