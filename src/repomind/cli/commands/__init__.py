"""Commands for RepoMind CLI."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Command(Protocol):
    """Command protocol。"""
    name: str
    aliases: list[str]
    description: str

    def execute(self, args: str) -> None:
        """Execute command。

        Args:
            args: Command arguments
        """
        ...


class CommandRegistry:
    """Command registry。"""

    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register command。

        Args:
            command: Command instance
        """
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Command | None:
        """Get command。

        Args:
            name: Command name or alias

        Returns:
            Command instance，如果不存在返回 None
        """
        return self._commands.get(name)

    def list_all(self) -> list[Command]:
        """List all commands (deduplicated)。

        Returns:
            Command list
        """
        seen: set[str] = set()
        result: list[Command] = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return result


# 全局Command registry
registry = CommandRegistry()
