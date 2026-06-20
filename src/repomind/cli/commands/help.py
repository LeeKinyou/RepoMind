"""Help command for RepoMind CLI."""
from dataclasses import dataclass, field

from repomind.cli.commands import registry


@dataclass
class HelpCommand:
    """Help command."""

    name: str = "/help"
    aliases: list[str] = field(default_factory=lambda: ["/?"])
    description: str = "Show help information"

    # Dependencies
    console: any = None

    def execute(self, args: str) -> None:
        """Execute help command.

        Args:
            args: Not used
        """
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        # Get all commands
        commands = registry.list_all()

        # Create table
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column(style="bold cyan", min_width=12)
        table.add_column(style="dim", min_width=8)
        table.add_column(style="white")

        for cmd in commands:
            aliases = ", ".join(cmd.aliases) if cmd.aliases else ""
            table.add_row(cmd.name, aliases, cmd.description)

        # Add natural language query hint
        table.add_row()
        table.add_row("[dim]<text>[/]", "", "[dim]Natural language query[/]")

        self.console.print(Panel(
            table,
            title="[bold cyan]Command Help[/]",
            border_style="cyan",
            padding=(1, 2),
        ))

        self.console.print()
        self.console.print("  [dim]Type text for natural language query[/]")
        self.console.print("  [dim]Use up/down arrows for command history[/]")
        self.console.print()


# Register command
def register_help_command(console):
    cmd = HelpCommand(console=console)
    registry.register(cmd)
