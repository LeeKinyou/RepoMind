"""Stats command for RepoMind CLI."""

from pathlib import Path
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.tables import show_index_stats


@dataclass
class StatsCommand:
    """Index stats command."""

    name: str = "/stats"
    aliases: list[str] = field(default_factory=lambda: ["/st"])
    description: str = "Show index statistics"

    # Dependencies
    console: any = None
    project_path: Path = None
    index_service: any = None

    def execute(self, args: str) -> None:
        """Execute stats command.

        Args:
            args: Unused
        """
        try:
            stats = self.index_service.get_stats()
            show_index_stats(self.console, stats)
        except Exception as e:
            self.console.print(
                Text(
                    f"  Failed to get stats: {e}",
                    style="red",
                )
            )


def register_stats_command(console, project_path, index_service):
    cmd = StatsCommand(
        console=console, project_path=project_path, index_service=index_service
    )
    registry.register(cmd)
