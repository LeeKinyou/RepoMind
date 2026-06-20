"""Index command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.tables import show_index_stats


@dataclass
class IndexCommand:
    """Index project command。"""

    name: str = "/index"
    aliases: list[str] = field(default_factory=lambda: ["/i"])
    description: str = "索引代码仓库"

    # 依赖注入
    console: any = None
    project_path: Path = None
    index_service: any = None

    def execute(self, args: str) -> None:
        """Execute index command。

        Args:
            args: Project path (optional, defaults to current)
        """
        from repomind.models.schemas import IndexOptions

        project = self.project_path
        if args:
            project = Path(args).resolve()

        if not project.exists():
            self.console.print(f"[red]Path not found: {project}[/]")
            return

        self.console.print(f"[dim]Indexing: {project}[/]")

        with show_spinner(self.console, "Indexing项目..."):
            result = self.index_service.index_directory(str(project), IndexOptions())

        if result.success:
            self.console.print()
            show_index_stats(self.console, {
                "files": result.indexed_files,
                "symbols": result.total_symbols,
                "classes": result.total_classes,
                "functions": result.total_functions,
                "imports": result.total_imports,
                "calls": result.total_calls,
            })
            self.console.print()
            self.console.print(f"[green]✅ Index complete，耗时 {result.elapsed_seconds:.2f}s[/]")
        else:
            self.console.print("[red]❌ Index failed:[/]")
            for err in result.errors:
                self.console.print(f"  [red]![/] {err}")


# 注册命令
def register_index_command(console, project_path, index_service):
    cmd = IndexCommand(console=console, project_path=project_path, index_service=index_service)
    registry.register(cmd)
