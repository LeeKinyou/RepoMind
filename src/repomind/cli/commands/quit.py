"""Quit command for RepoMind CLI."""

from dataclasses import dataclass, field

from repomind.cli.commands import registry


@dataclass
class QuitCommand:
    """Quit command."""

    name: str = "/quit"
    aliases: list[str] = field(default_factory=lambda: ["/exit", "/x"])
    description: str = "Exit program"

    # Dependencies
    console: any = None
    quit_callback: any = None

    def execute(self, args: str) -> None:
        """Execute quit command.

        Args:
            args: Not used
        """
        self.console.print("[dim]Goodbye![/]")
        if self.quit_callback:
            self.quit_callback()


# Register command
def register_quit_command(console, quit_callback):
    cmd = QuitCommand(console=console, quit_callback=quit_callback)
    registry.register(cmd)
