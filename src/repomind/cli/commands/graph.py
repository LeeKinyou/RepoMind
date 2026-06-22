"""Graph command for RepoMind CLI."""

from pathlib import Path
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.graph import show_call_graph


@dataclass
class GraphCommand:
    """Call graph command."""

    name: str = "/graph"
    aliases: list[str] = field(default_factory=lambda: ["/g"])
    description: str = "View call graph"

    # Dependencies
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """Execute call graph command.

        Args:
            args: Symbol name [--depth N] or [-d N]
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /graph <symbol-name> [--depth N | -d N]",
                    style="yellow",
                )
            )
            return

        # Parse args
        parts = args.split()
        name = parts[0]
        depth = 2

        for i, part in enumerate(parts):
            if part in ("--depth", "-d") and i + 1 < len(parts):
                try:
                    depth = int(parts[i + 1])
                except ValueError:
                    pass

        self._do_graph(name, depth)

    def _do_graph(self, name: str, depth: int = 2) -> None:
        """Display call graph.

        Args:
            name: Symbol name
            depth: Expansion depth
        """

        with show_spinner(self.console, "Searching..."):
            symbols = self.query_service.lookup_symbol(name, limit=1)

        if not symbols:
            self.console.print(
                Text(
                    f"  Not found: {name}",
                    style="yellow",
                )
            )
            return

        sym = symbols[0]
        graph_result = self.query_service.get_call_graph(
            sym.qualified_name, depth=depth
        )

        show_call_graph(self.console, graph_result, sym.qualified_name, depth)

        # Next-step suggestion
        hint = Text()
        hint.append("  Next: ", style="dim cyan")
        hint.append("/show ", style="cyan")
        hint.append(sym.name, style="white")
        hint.append(" for details, ", style="dim")
        hint.append("/graph ", style="cyan")
        hint.append(f"{sym.name} -d {depth + 1}", style="white")
        hint.append(" to expand depth", style="dim")
        self.console.print(hint)
        self.console.print()


def register_graph_command(console, project_path, query_service):
    cmd = GraphCommand(
        console=console, project_path=project_path, query_service=query_service
    )
    registry.register(cmd)
