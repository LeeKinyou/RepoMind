"""Stats command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.tables import show_index_stats


@dataclass
class StatsCommand:
    """Index stats command。"""

    name: str = "/stats"
    aliases: list[str] = field(default_factory=lambda: ["/st"])
    description: str = "显示索引统计"

    # 依赖注入
    console: any = None
    project_path: Path = None
    index_service: any = None

    def execute(self, args: str) -> None:
        """Execute stats command。

        Args:
            args: 未使用
        """
        try:
            stats = self.index_service.get_stats()
            self.console.print()
            show_index_stats(self.console, stats)
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]Failed to get stats: {e}[/]")


# 注册命令
def register_stats_command(console, project_path, index_service):
    cmd = StatsCommand(console=console, project_path=project_path, index_service=index_service)
    registry.register(cmd)
