"""REPL (Read-Eval-Print Loop) for RepoMind CLI.

Integrates:
- Dynamic context-aware prompt (project name + index status)
- Tab completion and command history (via prompt_toolkit)
- Fuzzy command correction for typos
- Onboarding wizard when project is not indexed
- Main menu dashboard on startup
- Project switching via /project command
"""

from __future__ import annotations

from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.table import Table
from rich.text import Text

import litellm
litellm.suppress_debug_info = True
litellm.telemetry = False

from repomind.cli.themes import REPOIND_THEME
from repomind.cli.components import show_banner
from repomind.cli.commands import registry
from repomind.cli.projects import ProjectRegistry
from repomind.cli.prompt_utils import (
    make_prompt_session,
    suggest_command,
    prompt_string,
)


class LazyServiceProxy:
    """A proxy that delays the instantiation of a service until an attribute is accessed."""
    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    def __getattr__(self, name):
        if self._instance is None:
            self._instance = self._factory()
        return getattr(self._instance, name)

    @property
    def _is_initialized(self):
        return self._instance is not None


class RepoMindREPL:
    """RepoMind interactive CLI."""

    def __init__(self, project_path: Path | None = None) -> None:
        """Initialize REPL.

        Args:
            project_path: Project path (defaults to current directory)
        """
        self.project = project_path or Path.cwd()
        self.console = Console(theme=REPOIND_THEME)
        self._should_quit = False
        self.project_registry = ProjectRegistry()
        self._prompt_session = None

        # Initialize services and commands for the initial project
        self._init_services()
        self._register_commands()

    def _init_services(self) -> None:
        """Initialize lazy service proxies for the current project."""
        index_dir = self.project / ".repomind"

        def make_index_service():
            from repomind.services.index_service import IndexService
            return IndexService(index_dir=str(index_dir))

        def make_query_service():
            from repomind.services.query_service import QueryService
            return QueryService(index_dir=str(index_dir))

        def make_rca_service():
            from repomind.services.rca_service import RCAService
            return RCAService(index_dir=str(index_dir))

        self.index_service = LazyServiceProxy(make_index_service)
        self.query_service = LazyServiceProxy(make_query_service)
        self.rca_service = LazyServiceProxy(make_rca_service)

    def _register_commands(self) -> None:
        """Register all commands for the current project."""
        # Clear existing registrations to support project switching
        registry._commands.clear()

        from repomind.cli.commands.index import register_index_command
        from repomind.cli.commands.query import register_query_command
        from repomind.cli.commands.show import register_show_command
        from repomind.cli.commands.graph import register_graph_command
        from repomind.cli.commands.callers import register_callers_command
        from repomind.cli.commands.callees import register_callees_command
        from repomind.cli.commands.stats import register_stats_command
        from repomind.cli.commands.help import register_help_command
        from repomind.cli.commands.quit import register_quit_command
        from repomind.cli.commands.rca import register_rca_command
        from repomind.cli.commands.project import register_project_command
        from repomind.cli.commands.ask import register_ask_command

        # Index completion callback updates the project registry
        def on_index_complete(result):
            try:
                self.project_registry.add(
                    self.project,
                    indexed=True,
                    file_count=result.indexed_files,
                    symbol_count=result.total_symbols,
                )
            except Exception:
                pass

        register_index_command(
            self.console,
            self.project,
            self.index_service,
            on_complete=on_index_complete,
        )
        register_query_command(self.console, self.project, self.query_service)
        register_ask_command(self.console, self.project, self.query_service)
        register_show_command(self.console, self.project, self.query_service)
        register_graph_command(self.console, self.project, self.query_service)
        register_callers_command(self.console, self.project, self.query_service)
        register_callees_command(self.console, self.project, self.query_service)
        register_stats_command(self.console, self.project, self.index_service)
        register_help_command(self.console)
        register_quit_command(self.console, self._set_quit)
        register_rca_command(self.console, self.project, self.rca_service)
        register_project_command(
            self.console,
            self.project_registry,
            self.project,
            self._switch_project,
        )

    def _switch_project(self, new_path: Path) -> None:
        """Switch to a different project.

        Args:
            new_path: New project path
        """
        self.project = new_path
        self._init_services()
        self._register_commands()
        # Reset prompt session to refresh completer
        self._prompt_session = None

        # Show new banner
        stats = self._get_stats()
        show_banner(self.console, self.project, stats, project_name=self.project.name)

    def _set_quit(self) -> None:
        """Set the quit flag."""
        self._should_quit = True

    def _get_stats(self) -> dict | None:
        """Get index statistics, returning None if not indexed."""
        try:
            # Check if index_service is already initialized
            if self.index_service._is_initialized:
                stats = self.index_service.get_stats()
            else:
                # Use SQLiteStore directly to avoid heavy imports on startup
                from repomind.storage.sqlite_store import SQLiteStore
                index_db = self.project / ".repomind" / "index.db"
                if not index_db.exists():
                    return None
                with SQLiteStore(str(index_db)) as store:
                    stats = store.get_stats()
            
            # Treat as "not indexed" if there are no files
            if not stats or stats.get("files", 0) == 0:
                return None
            return stats
        except Exception:
            return None

    def _is_indexed(self) -> bool:
        """Check if the current project is indexed."""
        return self._get_stats() is not None

    def _get_prompt_session(self):
        """Lazily create the prompt session with current commands."""
        if self._prompt_session is None:
            commands = [cmd.name for cmd in registry.list_all()]
            # Also include aliases for completion
            for cmd in registry.list_all():
                commands.extend(cmd.aliases)
            history_path = self.project / ".repomind" / "history"
            self._prompt_session = make_prompt_session(
                history_path=history_path,
                commands=commands,
            )
        return self._prompt_session

    def _handle_input(self, text: str) -> None:
        """Handle user input.

        Args:
            text: User input text
        """
        text = text.strip()
        if not text:
            return

        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._handle_query(text)

    def _handle_command(self, text: str) -> None:
        """Handle a slash command, with fuzzy correction for typos.

        Args:
            text: Command text (starts with /)
        """
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = registry.get(cmd_name)
        if cmd:
            cmd.execute(args)
            return

        # Fuzzy correction — suggest the closest matching command
        all_commands = [cmd.name for cmd in registry.list_all()]
        for c in registry.list_all():
            all_commands.extend(c.aliases)

        suggestion = suggest_command(cmd_name, all_commands)
        if suggestion:
            line = Text()
            line.append("  Unknown command: ", style="red")
            line.append(cmd_name, style="bold red")
            line.append(". Did you mean ", style="dim")
            line.append(suggestion, style="cyan")
            line.append("?", style="dim")
            self.console.print(line)

            line2 = Text()
            line2.append("  Type ", style="dim")
            line2.append("/help", style="cyan")
            line2.append(" for all commands", style="dim")
            self.console.print(line2)
        else:
            self.console.print(
                Text(
                    f"  Unknown command: {cmd_name}",
                    style="red",
                )
            )
            self.console.print(
                Text(
                    "  Type /help for available commands",
                    style="dim",
                )
            )

    def _handle_query(self, query: str) -> None:
        """Handle natural language query.

        Args:
            query: Query text
        """
        cmd = registry.get("/ask")
        if cmd:
            cmd.execute(query)

    def _show_onboarding(self) -> None:
        """Show onboarding wizard when project is not indexed."""
        line = Text("  Start with ", style="muted")
        line.append("/index", style="command")
        line.append(
            " - it builds the local symbol and call graph index.", style="muted"
        )
        self.console.print(line)
        self.console.print()

    def _show_dashboard(self) -> None:
        """Show the highest-value actions for the current workspace."""
        content_width = min(68, max(36, self.console.width - 4))
        actions = (
            [
                ("Ask a question", "type natural language"),
                ("/graph <symbol>", "inspect call relationships"),
                ("/index", "rebuild repository index"),
                ("/help", "show every command"),
            ]
            if self._is_indexed()
            else [
                ("/index", "build the repository index"),
                ("Ask a question", "search after indexing"),
                ("/project", "open another workspace"),
                ("/help", "show every command"),
            ]
        )

        action_table = Table.grid(padding=(0, 2))
        action_table.add_column(style="command", min_width=20, no_wrap=True)
        action_table.add_column(style="muted")
        for action, description in actions:
            action_table.add_row(action, description)

        content = Table.grid()
        content.width = content_width
        content.add_row(Text("Start here", style="bold white"))
        content.add_row("")
        content.add_row(action_table)
        self.console.print(Align.center(content))
        self.console.print()

    def run(self) -> None:
        """Run the REPL main loop."""
        # Show banner
        stats = self._get_stats()
        show_banner(self.console, self.project, stats, project_name=self.project.name)

        # Onboarding if not indexed
        if not stats:
            self._show_onboarding()

        # Show quick actions dashboard
        self._show_dashboard()

        # Ensure the project is in the registry
        try:
            self.project_registry.add(
                self.project,
                indexed=stats is not None,
                file_count=stats.get("files", 0) if stats else 0,
                symbol_count=stats.get("symbols", 0) if stats else 0,
            )
        except Exception:
            pass

        # Main loop
        while not self._should_quit:
            try:
                session = self._get_prompt_session()
                prompt_text = prompt_string(self.project.name, self._is_indexed())
                user_input = session.prompt(prompt_text)
                self._handle_input(user_input)
            except KeyboardInterrupt:
                self.console.print(
                    Text(
                        "  Type /quit to exit",
                        style="dim",
                    )
                )
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(
                    Text(
                        f"  Error: {e}",
                        style="red",
                    )
                )

        self.console.print(Text("  Goodbye!", style="dim"))


def run_repl(project_path: Path | None = None) -> None:
    """Run the REPL.

    Args:
        project_path: Project path
    """
    repl = RepoMindREPL(project_path)
    repl.run()
