"""Help command for RepoMind CLI."""

from dataclasses import dataclass, field

from repomind.cli.commands import registry


@dataclass
class HelpCommand:
    """Help command."""

    name: str = "/help"
    aliases: list[str] = field(default_factory=lambda: ["/?", "/h"])
    description: str = "Show help information"

    # Dependencies
    console: any = None

    def execute(self, args: str) -> None:
        """Execute help command.

        Args:
            args: Not used
        """
        from rich.table import Table
        from rich.text import Text
        from rich.rule import Rule

        # Header
        self.console.print()
        header = Text()
        header.append("  Commands", style="bold cyan")
        self.console.print(header)
        self.console.print(Rule(style="dim", characters="─"))

        # Build a clean command table — no inner borders
        table = Table(
            box=None,
            show_header=False,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column(style="bold cyan", min_width=12)
        table.add_column(style="dim", min_width=10)
        table.add_column(style="white")

        commands = registry.list_all()
        for cmd in commands:
            aliases = ", ".join(cmd.aliases) if cmd.aliases else ""
            table.add_row(cmd.name, aliases, cmd.description)

        # Add natural language query hint
        table.add_row()
        table.add_row("<text>", "", "Natural language query")

        self.console.print(table)
        self.console.print()

        # Usage hints
        hint1 = Text()
        hint1.append("  Tip: ", style="dim cyan")
        hint1.append("type a question to search, or ", style="dim")
        hint1.append("/<command>", style="cyan")
        hint1.append(" to run a command", style="dim")
        self.console.print(hint1)

        hint2 = Text()
        hint2.append("  Tab", style="dim cyan")
        hint2.append(" completes commands, ", style="dim")
        hint2.append("↑/↓", style="dim cyan")
        hint2.append(" navigates history", style="dim")
        self.console.print(hint2)
        self.console.print()


# Register command
def register_help_command(console):
    cmd = HelpCommand(console=console)
    registry.register(cmd)
