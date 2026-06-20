"""RCA command for RepoMind CLI."""
from pathlib import Path
from dataclasses import dataclass, field

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.rca import show_rca_result, show_rca_trace_input


@dataclass
class RCACommand:
    """RCA command。"""

    name: str = "/rca"
    aliases: list[str] = field(default_factory=lambda: ["/r"])
    description: str = "根因分析"

    # 依赖注入
    console: any = None
    project_path: Path = None
    rca_service: any = None

    def execute(self, args: str) -> None:
        """Execute RCA command。

        Args:
            args: Trace file path (optional), enters interactive mode if not provided
        """
        if args:
            # 从文件读取 trace
            file_path = Path(args)
            if not file_path.exists():
                self.console.print(f"[red]File not found: {args}[/]")
                return
            trace = file_path.read_text(encoding="utf-8")
            self._analyze_trace(trace)
        else:
            # 交互模式
            self._interactive_mode()

    def _interactive_mode(self) -> None:
        """交互式 RCA 模式。"""
        show_rca_trace_input(self.console)

        lines = []
        empty_count = 0

        while True:
            try:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break

        trace = "\n".join(lines).strip()
        if not trace:
            self.console.print("[dim]Cancelled[/]")
            return

        self._analyze_trace(trace)

    def _analyze_trace(self, trace: str) -> None:
        """分析 trace。"""
        with show_spinner(self.console, "Analyzing..."):
            result = self.rca_service.analyze_trace(trace)

        self.console.print()
        show_rca_result(self.console, result)
        self.console.print()


# 注册命令
def register_rca_command(console, project_path, rca_service):
    cmd = RCACommand(console=console, project_path=project_path, rca_service=rca_service)
    registry.register(cmd)
