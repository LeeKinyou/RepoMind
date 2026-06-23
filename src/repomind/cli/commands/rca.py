"""RCA command for RepoMind CLI."""

from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from rich.text import Text

from repomind.cli.commands import registry
from repomind.cli.components.progress import show_spinner
from repomind.cli.components.rca import show_rca_result, show_rca_trace_input


@dataclass
class RCACommand:
    """RCA command."""

    name: str = "/rca"
    aliases: list[str] = field(default_factory=lambda: ["/r"])
    description: str = "Root cause analysis from stack trace"

    # Dependencies
    console: Any = None
    project_path: Path = None
    rca_service: Any = None

    def execute(self, args: str) -> None:
        """Execute RCA command.

        Args:
            args: Trace file path (optional) and options (e.g. --mode agent), enters interactive mode if no path provided
        """
        import shlex
        parsed_args = shlex.split(args) if args else []
        
        mode = "evidence"
        if "--mode" in parsed_args:
            idx = parsed_args.index("--mode")
            if idx + 1 < len(parsed_args):
                mode = parsed_args[idx + 1]
                parsed_args.pop(idx + 1)
            parsed_args.pop(idx)
            
        file_path_str = parsed_args[0] if parsed_args else None

        if file_path_str:
            # Read trace from file
            file_path = Path(file_path_str)
            if not file_path.exists():
                self.console.print(
                    Text(
                        f"  File not found: {file_path_str}",
                        style="red",
                    )
                )
                return
            trace = file_path.read_text(encoding="utf-8")
            self._analyze_trace(trace, mode)
        else:
            # Interactive mode
            self._interactive_mode(mode)

    def _interactive_mode(self, mode: str) -> None:
        """Interactive RCA mode — multi-line trace input."""
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
            self.console.print(Text("  Cancelled.", style="dim"))
            return

        self._analyze_trace(trace, mode)

    def _analyze_trace(self, trace: str, mode: str) -> None:
        """Analyze trace.

        Args:
            trace: Stack trace text
            mode: 'evidence' or 'agent'
        """
        if mode == "agent":
            from repomind.agent.diagnostic_agent import DiagnosticAgent
            from repomind.reporter.evidence_report import EvidenceReporter
            
            with show_spinner(self.console, "Running Diagnostic Agent loop..."):
                agent = DiagnosticAgent(index_dir=str(self.project_path / ".repomind"))
                state = agent.run(trace)
                
            report = EvidenceReporter.generate_agent_report(state)
            self.console.print()
            # In REPL, just print the report directly since we don't have a show_agent_result yet
            import rich.markdown
            self.console.print(rich.markdown.Markdown(report))
        else:
            with show_spinner(self.console, "Analyzing..."):
                result = self.rca_service.analyze_trace(trace)

            show_rca_result(self.console, result)

            # Next-step suggestion
            if result.affected_symbols:
                hint = Text()
                hint.append("  Next: ", style="dim cyan")
                hint.append("/show ", style="cyan")
                hint.append(result.affected_symbols[0].name, style="white")
                hint.append(" to inspect the suspected symbol", style="dim")
                self.console.print(hint)
                self.console.print()


def register_rca_command(console, project_path, rca_service):
    cmd = RCACommand(
        console=console, project_path=project_path, rca_service=rca_service
    )
    registry.register(cmd)
