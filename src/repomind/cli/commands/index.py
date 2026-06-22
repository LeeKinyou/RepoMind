"""Index command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text
from rich.rule import Rule
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

from repomind.cli.commands import registry
from repomind.cli.components.tables import show_index_stats


@dataclass
class IndexCommand:
    """Index project command."""

    name: str = "/index"
    aliases: list[str] = field(default_factory=lambda: ["/i"])
    description: str = "Index code repository"

    # Dependencies
    console: Any = None
    project_path: Path = None
    index_service: Any = None
    on_complete: Any = None  # callback invoked after successful indexing

    def execute(self, args: str) -> None:
        """Execute index command.

        Args:
            args: Project path (optional, defaults to current project)
        """
        from repomind.models.schemas import IndexOptions

        project = self.project_path
        if args:
            project = Path(args).resolve()

        if not project.exists():
            self.console.print(
                Text(
                    f"  Path not found: {project}",
                    style="red",
                )
            )
            return

        # Header
        self.console.print()
        header = Text()
        header.append("  Indexing ", style="bold cyan")
        header.append(str(project), style="white")
        self.console.print(header)
        self.console.print(Rule(style="dim", characters="─"))

        # Multi-step progress feedback
        self._run_index_with_progress(project, IndexOptions())

    def _run_index_with_progress(self, project: Path, options) -> None:
        """Run indexing with multi-step progress display.

        Args:
            project: Project path
            options: Index options
        """

        # Use a progress display with steps
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        ) as progress:
            # Step 1: scanning files
            step1 = progress.add_task("[cyan]Scanning files...", total=None)
            result = self.index_service.index_directory(str(project), options)
            progress.update(step1, completed=1, total=1)

        # Show results
        if result.success:
            self.console.print()
            show_index_stats(
                self.console,
                {
                    "files": result.indexed_files,
                    "symbols": result.total_symbols,
                    "classes": result.total_classes,
                    "functions": result.total_functions,
                    "imports": result.total_imports,
                    "calls": result.total_calls,
                },
            )

            done = Text()
            done.append("  Indexed in ", style="green")
            done.append(f"{result.elapsed_seconds:.2f}s", style="bold green")
            if result.errors:
                done.append(f"  ({len(result.errors)} warnings)", style="yellow")
            self.console.print(done)
            self.console.print()

            # Next-step suggestion
            hint = Text()
            hint.append("  Next: ", style="dim cyan")
            hint.append("type a question to search, or ", style="dim")
            hint.append("/stats", style="cyan")
            hint.append(" for details", style="dim")
            self.console.print(hint)
            self.console.print()

            # Notify completion callback (for project registry update)
            if self.on_complete:
                try:
                    self.on_complete(result)
                except Exception:
                    pass
        else:
            self.console.print()
            self.console.print(Text("  Index failed:", style="red"))
            for err in result.errors:
                self.console.print(Text(f"    ! {err}", style="red"))
            self.console.print()


def register_index_command(console, project_path, index_service, on_complete=None):
    cmd = IndexCommand(
        console=console,
        project_path=project_path,
        index_service=index_service,
        on_complete=on_complete,
    )
    registry.register(cmd)
