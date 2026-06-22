"""Ask command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text
from rich.markdown import Markdown

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.models.schemas import QueryOptions


@dataclass
class AskCommand:
    """Ask command."""

    name: str = "/ask"
    aliases: list[str] = field(default_factory=list)
    description: str = "Ask a natural language question to the LLM"

    # Dependencies
    console: Any = None
    project_path: Path = None
    query_service: Any = None

    def execute(self, args: str) -> None:
        """Execute ask command.

        Args:
            args: Query text
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /ask <question>  (or just type your question)",
                    style="yellow",
                )
            )
            return

        self._do_ask(args)

    def _do_ask(self, query: str) -> None:
        """Execute ask.

        Args:
            query: Query text
        """
        # First retrieve context
        with show_spinner(self.console, "Retrieving context..."):
            result = self.query_service.search(query, QueryOptions(max_results=10, include_code=True))

        if not result.symbols:
            self.console.print(
                Text(
                    f"  No relevant context found in the codebase to answer '{query}'.",
                    style="yellow",
                )
            )
            
        self.console.print()
        self.console.print("  [bold cyan]LLM Answer:[/bold cyan]")
        with show_spinner(self.console, "Generating answer..."):
            llm_ans = self.query_service.answer(query, result)
        
        self.console.print(Markdown(llm_ans))
        self.console.print()


def register_ask_command(console, project_path, query_service):
    cmd = AskCommand(
        console=console,
        project_path=project_path,
        query_service=query_service,
    )
    registry.register(cmd)
