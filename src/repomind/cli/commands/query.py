"""Query command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.tables import show_search_results


@dataclass
class QueryCommand:
    """Query command。"""

    name: str = "/query"
    aliases: list[str] = field(default_factory=lambda: ["/q", "/search"])
    description: str = "精确查询符号"

    # 依赖注入
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """执行Query command。

        Args:
            args: Query text
        """
        if not args:
            self.console.print("[yellow]请提供Query text[/]")
            return

        self._do_query(args)

    def _do_query(self, query: str, top_k: int = 10) -> None:
        """执行查询。"""
        from repomind.models.schemas import QueryOptions

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(query, QueryOptions(max_results=top_k))

        show_search_results(
            self.console,
            query,
            result.symbols,
            result.elapsed_seconds,
            str(self.project_path),
        )


# 注册命令
def register_query_command(console, project_path, query_service):
    cmd = QueryCommand(console=console, project_path=project_path, query_service=query_service)
    registry.register(cmd)
