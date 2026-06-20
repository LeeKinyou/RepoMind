"""Graph command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.graph import show_call_graph


@dataclass
class GraphCommand:
    """Call graph command。"""

    name: str = "/graph"
    aliases: list[str] = field(default_factory=lambda: ["/g"])
    description: str = "查看调用图"

    # 依赖注入
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """执行Call graph command。

        Args:
            args: Symbol name [--depth N]
        """
        if not args:
            self.console.print("[yellow]请提供Symbol name[/]")
            return

        # 解析参数
        parts = args.split()
        name = parts[0]
        depth = 2

        for i, part in enumerate(parts):
            if part == "--depth" and i + 1 < len(parts):
                try:
                    depth = int(parts[i + 1])
                except ValueError:
                    pass

        self._do_graph(name, depth)

    def _do_graph(self, name: str, depth: int = 2) -> None:
        """显示调用图。"""
        from repomind.models.schemas import QueryOptions

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(name, QueryOptions(max_results=1))

        if not result.symbols:
            self.console.print(f"[yellow]Not found: {name}[/]")
            return

        sym = result.symbols[0]
        graph_result = self.query_service.get_call_graph(sym.qualified_name, depth=depth)

        show_call_graph(self.console, graph_result, sym.qualified_name, depth)


# 注册命令
def register_graph_command(console, project_path, query_service):
    cmd = GraphCommand(console=console, project_path=project_path, query_service=query_service)
    registry.register(cmd)
