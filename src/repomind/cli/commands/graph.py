"""Interactive browser graph command for RepoMind CLI."""

import webbrowser
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.graph_html import write_graph_html


@dataclass
class GraphCommand:
    """Open a real interactive directed call graph."""

    name: str = "/graph"
    aliases: list[str] = field(default_factory=lambda: ["/g"])
    description: str = "Open interactive call graph in browser"

    # Dependencies
    console: Any = None
    project_path: Path = None
    query_service: Any = None

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
        """Generate and open an interactive call graph.

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

        output_dir = self.project_path / ".repomind" / "visualizations"
        output_path = write_graph_html(
            graph_result,
            sym.qualified_name,
            depth,
            output_dir,
        )
        opened = webbrowser.open(output_path.resolve().as_uri())

        result = Text()
        result.append("  Graph written to ", style="dim")
        result.append(str(output_path), style="cyan")
        result.append(
            f"  ({len(graph_result.nodes)} nodes, {len(graph_result.edges)} edges)",
            style="dim",
        )
        self.console.print(result)

        if not opened:
            self.console.print(
                Text(
                    "  Browser could not be opened automatically; open the file above.",
                    style="yellow",
                )
            )

        hint = Text("  Terminal tree: ", style="dim")
        hint.append(f"/tree {sym.name} -d {depth}", style="cyan")
        self.console.print(hint)
        self.console.print()


def register_graph_command(console, project_path, query_service):
    cmd = GraphCommand(
        console=console, project_path=project_path, query_service=query_service
    )
    registry.register(cmd)
