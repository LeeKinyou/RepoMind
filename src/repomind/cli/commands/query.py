"""Query command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.tables import show_search_results


@dataclass
class QueryCommand:
    """Query command."""

    name: str = "/query"
    aliases: list[str] = field(default_factory=lambda: ["/q", "/search"])
    description: str = "Search symbols by natural language or keyword"

    # Dependencies
    console: Any = None
    project_path: Path = None
    query_service: Any = None
    interactive: bool = True  # enable interactive number selection

    def execute(self, args: str) -> None:
        """Execute query command.

        Args:
            args: Query text
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /query <text>  (or just type your question)",
                    style="yellow",
                )
            )
            return

        self._do_query(args)

    def _do_query(self, query: str, top_k: int = 10) -> None:
        """Execute query and optionally enter interactive selection.

        Args:
            query: Query text
            top_k: Max results
        """
        from repomind.models.schemas import QueryOptions

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(query, QueryOptions(max_results=top_k))

        results = show_search_results(
            self.console,
            query,
            result.symbols,
            result.elapsed_seconds,
            str(self.project_path),
        )

        # Interactive number selection
        if self.interactive and results:
            self._interactive_select(results)

    def _interactive_select(self, results) -> None:
        """Offer interactive number selection for search results.

        Args:
            results: List of SymbolInfo results
        """
        prompt_text = Text()
        prompt_text.append(
            "  Enter number to view details, or Enter to continue: ", style="cyan"
        )
        self.console.print(prompt_text, end="")

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print()
            return

        if not choice:
            return

        try:
            idx = int(choice)
        except ValueError:
            return

        if 1 <= idx <= len(results):
            sym = results[idx - 1]
            # Delegate to /show command for the selected symbol
            show_cmd = registry.get("/show")
            if show_cmd:
                self.console.print()
                show_cmd.execute(sym.name)
        else:
            self.console.print(
                Text(
                    f"  Invalid number (1-{len(results)})",
                    style="yellow",
                )
            )


def register_query_command(
    console, project_path, query_service, interactive: bool = True
):
    cmd = QueryCommand(
        console=console,
        project_path=project_path,
        query_service=query_service,
        interactive=interactive,
    )
    registry.register(cmd)
