"""Project command for RepoMind CLI — list, switch, add, remove projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from rich.text import Text
from rich.table import Table
from rich.rule import Rule

from repomind.cli.commands import registry
from repomind.cli.projects import ProjectRegistry, ProjectEntry


@dataclass
class ProjectCommand:
    """Project management command — list, switch, add, remove."""

    name: str = "/project"
    aliases: list[str] = field(default_factory=lambda: ["/proj", "/pj"])
    description: str = "List or switch projects (/project [list|switch|add|remove])"

    # Dependencies
    console: any = None
    registry: ProjectRegistry = None
    switch_callback: Callable[[Path], None] = None
    current_path: Path = None

    def execute(self, args: str) -> None:
        """Execute project command.

        Args:
            args: Subcommand and arguments. One of:
                  - "" or "list": list all projects
                  - "switch <name|index>": switch to a project
                  - "add [path]": add current or given project
                  - "remove <name|index>": remove a project
        """
        parts = args.split(maxsplit=1) if args else []
        sub = parts[0].lower() if parts else "list"
        sub_args = parts[1] if len(parts) > 1 else ""

        if sub == "list":
            self._list()
        elif sub == "switch":
            self._switch(sub_args)
        elif sub == "add":
            self._add(sub_args)
        elif sub == "remove":
            self._remove(sub_args)
        else:
            # Treat unknown sub as a project name to switch to
            self._switch(args)

    def _list(self) -> None:
        """List all registered projects."""
        projects = self.registry.list_all()

        # Header
        self.console.print()
        header = Text()
        header.append("  Projects", style="bold cyan")
        self.console.print(header)
        self.console.print(Rule(style="dim", characters="─"))

        if not projects:
            empty = Text()
            empty.append("  No registered projects. Use ", style="dim")
            empty.append("/project add", style="cyan")
            empty.append(" to add one.", style="dim")
            self.console.print(empty)
            self.console.print()
            return

        table = Table(
            box=None,
            show_header=False,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column(style="dim", min_width=4)
        table.add_column(style="bold white", min_width=16)
        table.add_column(style="dim", min_width=8)
        table.add_column(style="dim cyan")

        current_resolved = str(self.current_path.resolve()) if self.current_path else ""

        for i, entry in enumerate(projects, 1):
            marker = "*" if entry.path == current_resolved else " "
            status = "indexed" if entry.indexed else "not indexed"
            stats = ""
            if entry.indexed:
                stats = f"{entry.file_count:,} files · {entry.symbol_count:,} symbols"
            table.add_row(
                f"{marker}{i}",
                entry.name,
                status,
                f"{entry.path}  {stats}",
            )

        self.console.print(table)
        self.console.print()

        hint = Text()
        hint.append("  Tip: ", style="dim cyan")
        hint.append("/project switch <name|n>", style="cyan")
        hint.append(" to switch projects", style="dim")
        self.console.print(hint)
        self.console.print()

    def _switch(self, target: str) -> None:
        """Switch to a different project.

        Args:
            target: Project name or 1-based index number
        """
        if not target:
            self.console.print(
                Text(
                    "  Usage: /project switch <name|number>",
                    style="yellow",
                )
            )
            return

        projects = self.registry.list_all()
        if not projects:
            self.console.print(
                Text(
                    "  No registered projects to switch to.",
                    style="yellow",
                )
            )
            return

        entry = self._find_project(target, projects)
        if entry is None:
            self.console.print(
                Text(
                    f"  Project not found: {target}",
                    style="red",
                )
            )
            return

        new_path = Path(entry.path)
        if not new_path.exists():
            self.console.print(
                Text(
                    f"  Path no longer exists: {new_path}",
                    style="red",
                )
            )
            return

        if self.switch_callback:
            self.console.print(
                Text(
                    f"  Switching to {entry.name}...",
                    style="dim",
                )
            )
            self.switch_callback(new_path)
        else:
            self.console.print(
                Text(
                    f"  Would switch to: {entry.name} ({new_path})",
                    style="cyan",
                )
            )

    def _add(self, path_str: str) -> None:
        """Add a project to the registry.

        Args:
            path_str: Path to add (defaults to current project path)
        """
        target = Path(path_str).resolve() if path_str else self.current_path
        if not target.exists():
            self.console.print(
                Text(
                    f"  Path not found: {target}",
                    style="red",
                )
            )
            return

        # Check for an existing index to populate stats
        index_dir = target / ".repomind"
        indexed = index_dir.exists()
        file_count = 0
        symbol_count = 0
        if indexed:
            try:
                from repomind.storage.sqlite_store import SQLiteStore

                store = SQLiteStore(str(index_dir / "index.db"))
                stats = store.get_stats()
                file_count = stats.get("files", 0)
                symbol_count = stats.get("symbols", 0)
                store.close()
            except Exception:
                pass

        entry = self.registry.add(
            target, indexed=indexed, file_count=file_count, symbol_count=symbol_count
        )
        self.console.print(
            Text(
                f"  Added project: {entry.name} ({entry.path})",
                style="green",
            )
        )
        self.console.print()

    def _remove(self, target: str) -> None:
        """Remove a project from the registry.

        Args:
            target: Project name or 1-based index number
        """
        if not target:
            self.console.print(
                Text(
                    "  Usage: /project remove <name|number>",
                    style="yellow",
                )
            )
            return

        projects = self.registry.list_all()
        entry = self._find_project(target, projects)
        if entry is None:
            self.console.print(
                Text(
                    f"  Project not found: {target}",
                    style="red",
                )
            )
            return

        if self.registry.remove(entry.path):
            self.console.print(
                Text(
                    f"  Removed project: {entry.name}",
                    style="green",
                )
            )
        else:
            self.console.print(
                Text(
                    f"  Failed to remove: {entry.name}",
                    style="red",
                )
            )
        self.console.print()

    def _find_project(
        self,
        target: str,
        projects: list[ProjectEntry],
    ) -> ProjectEntry | None:
        """Find a project by name or 1-based index.

        Args:
            target: Project name or index string
            projects: List of projects to search

        Returns:
            Matching project entry or None
        """
        # Try numeric index first
        try:
            idx = int(target)
            if 1 <= idx <= len(projects):
                return projects[idx - 1]
        except ValueError:
            pass

        # Try exact name match (case-insensitive)
        target_lower = target.lower()
        for entry in projects:
            if entry.name.lower() == target_lower:
                return entry

        # Try path match
        try:
            resolved = str(Path(target).resolve())
            for entry in projects:
                if entry.path == resolved:
                    return entry
        except (OSError, ValueError):
            pass

        return None


def register_project_command(
    console,
    project_registry: ProjectRegistry,
    current_path: Path,
    switch_callback: Callable[[Path], None],
):
    """Register the project command.

    Args:
        console: Rich console
        project_registry: Project registry instance
        current_path: Current project path
        switch_callback: Callback invoked with the new project path
    """
    cmd = ProjectCommand(
        console=console,
        registry=project_registry,
        switch_callback=switch_callback,
        current_path=current_path,
    )
    registry.register(cmd)
