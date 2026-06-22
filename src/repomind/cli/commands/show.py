"""Show command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text
from rich.rule import Rule

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.tables import show_symbol_detail, show_paged_source


@dataclass
class ShowCommand:
    """Show symbol detail command."""

    name: str = "/show"
    aliases: list[str] = field(default_factory=lambda: ["/s"])
    description: str = "Show symbol details"

    # Dependencies
    console: Any = None
    project_path: Path = None
    query_service: Any = None

    def execute(self, args: str) -> None:
        """Execute show command.

        Args:
            args: Symbol name
        """
        if not args:
            self.console.print(
                Text(
                    "  Usage: /show <symbol-name>",
                    style="yellow",
                )
            )
            return

        self._do_show(args)

    def _do_show(self, name: str) -> None:
        """Display symbol details with paginated source code.

        Args:
            name: Symbol name to look up
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

        # Get call relations
        callers = self.query_service.get_callers(sym.qualified_name)
        callees = self.query_service.get_callees(sym.qualified_name)

        # Read source code
        source_code = None
        try:
            file_path = Path(sym.file_path)
            if file_path.exists():
                lines = file_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                start = max(0, sym.start_line - 1)
                end = min(len(lines), sym.end_line)
                source_code = "\n".join(lines[start:end])
        except Exception:
            pass

        # Display detail (without source — we'll page it separately if long)
        source_lines = source_code.count("\n") + 1 if source_code else 0
        if source_code and source_lines > 40:
            # Show metadata + docs + relations first, then paged source
            show_symbol_detail(self.console, sym, callers, callees, source_code=None)
            self.console.print(Text("  Source", style="bold"))
            self.console.print(Rule(style="dim", characters="─"))
            show_paged_source(self.console, source_code, sym.start_line)
            self.console.print()
        else:
            show_symbol_detail(self.console, sym, callers, callees, source_code)

        # Next-step suggestion
        hint = Text()
        hint.append("  Next: ", style="dim cyan")
        hint.append("/graph ", style="cyan")
        hint.append(sym.name, style="white")
        hint.append(" for call graph, ", style="dim")
        hint.append("/callers", style="cyan")
        hint.append(" or ", style="dim")
        hint.append("/callees", style="cyan")
        hint.append(" for relations", style="dim")
        self.console.print(hint)
        self.console.print()


def register_show_command(console, project_path, query_service):
    cmd = ShowCommand(
        console=console, project_path=project_path, query_service=query_service
    )
    registry.register(cmd)
