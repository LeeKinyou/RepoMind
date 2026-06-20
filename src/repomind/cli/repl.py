"""REPL (Read-Eval-Print Loop) for RepoMind CLI."""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

from repomind.cli.themes import REPOIND_THEME
from repomind.cli.components import show_banner
from repomind.cli.commands import registry


class RepoMindREPL:
    """RepoMind 交互式命令行界面。"""

    def __init__(self, project_path: Path | None = None):
        """初始化 REPL。

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project = project_path or Path.cwd()
        self.console = Console(theme=REPOIND_THEME)
        self._should_quit = False

        # 初始化服务
        self._init_services()

        # 注册命令
        self._register_commands()

    def _init_services(self) -> None:
        """初始化服务。"""
        from repomind.services.index_service import IndexService
        from repomind.services.query_service import QueryService
        from repomind.services.rca_service import RCAService

        index_dir = self.project / ".repomind"

        self.index_service = IndexService(index_dir=str(index_dir))
        self.query_service = QueryService(index_dir=str(index_dir))
        self.rca_service = RCAService(index_dir=str(index_dir))

    def _register_commands(self) -> None:
        """注册所有命令。"""
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

        # 注册命令
        register_index_command(self.console, self.project, self.index_service)
        register_query_command(self.console, self.project, self.query_service)
        register_show_command(self.console, self.project, self.query_service)
        register_graph_command(self.console, self.project, self.query_service)
        register_callers_command(self.console, self.project, self.query_service)
        register_callees_command(self.console, self.project, self.query_service)
        register_stats_command(self.console, self.project, self.index_service)
        register_help_command(self.console)
        register_quit_command(self.console, self._set_quit)
        register_rca_command(self.console, self.project, self.rca_service)

    def _set_quit(self) -> None:
        """设置退出标志。"""
        self._should_quit = True

    def _get_stats(self) -> dict | None:
        """获取索引统计。"""
        try:
            return self.index_service.get_stats()
        except Exception:
            return None

    def _handle_input(self, text: str) -> None:
        """处理用户输入。

        Args:
            text: 用户输入文本
        """
        text = text.strip()
        if not text:
            return

        if text.startswith('/'):
            self._handle_command(text)
        else:
            self._handle_query(text)

    def _handle_command(self, text: str) -> None:
        """处理命令。

        Args:
            text: 命令文本（以 / 开头）
        """
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = registry.get(cmd_name)
        if cmd:
            cmd.execute(args)
        else:
            self.console.print(f"[red]Unknown command: {cmd_name}[/]")
            self.console.print("Type [cyan]/help[/] for available commands")

    def _handle_query(self, query: str) -> None:
        """处理自然语言查询。

        Args:
            query: 查询文本
        """
        from repomind.cli.commands.query import QueryCommand

        # 找到查询命令并执行
        cmd = registry.get("/query")
        if cmd:
            cmd.execute(query)

    def run(self) -> None:
        """运行 REPL。"""
        # 显示横幅
        stats = self._get_stats()
        show_banner(self.console, self.project, stats)

        # 主循环
        while not self._should_quit:
            try:
                # 使用 Rich 控制台读取输入
                self.console.print()
                user_input = self.console.input("[bold green]>[/] ")
                self._handle_input(user_input)
            except KeyboardInterrupt:
                self.console.print("\n[dim]Type /quit to exit[/]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")

        self.console.print("[dim]Goodbye![/]")


def run_repl(project_path: Path | None = None) -> None:
    """运行 REPL 的便捷函数。

    Args:
        project_path: 项目路径
    """
    repl = RepoMindREPL(project_path)
    repl.run()
