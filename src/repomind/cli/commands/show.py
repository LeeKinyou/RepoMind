"""Show command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.tables import show_symbol_detail


@dataclass
class ShowCommand:
    """Show symbol detail command。"""

    name: str = "/show"
    aliases: list[str] = field(default_factory=lambda: ["/s"])
    description: str = "查看符号详情"

    # 依赖注入
    console: any = None
    project_path: Path = None
    query_service: any = None

    def execute(self, args: str) -> None:
        """Execute show command。

        Args:
            args: Symbol name
        """
        if not args:
            self.console.print("[yellow]请提供Symbol name[/]")
            return

        self._do_show(args)

    def _do_show(self, name: str) -> None:
        """显示符号详情。"""
        from repomind.models.schemas import QueryOptions

        with show_spinner(self.console, "Searching..."):
            result = self.query_service.search(name, QueryOptions(max_results=1))

        if not result.symbols:
            self.console.print(f"[yellow]Not found: {name}[/]")
            return

        sym = result.symbols[0]

        # 获取调用关系
        callers = self.query_service.get_callers(sym.qualified_name)
        callees = self.query_service.get_callees(sym.qualified_name)

        # 读取源代码
        source_code = None
        try:
            file_path = Path(sym.file_path)
            if file_path.exists():
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, sym.start_line - 1)
                end = min(len(lines), sym.end_line)
                source_code = "\n".join(lines[start:end])
        except Exception:
            pass

        show_symbol_detail(self.console, sym, callers, callees, source_code)


# 注册命令
def register_show_command(console, project_path, query_service):
    cmd = ShowCommand(console=console, project_path=project_path, query_service=query_service)
    registry.register(cmd)
