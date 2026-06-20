"""RCA service - root cause analysis from stack traces."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from repomind.models.schemas import RCAResult, SymbolInfo, safe_symbol_type
from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore
from repomind.utils.path_utils import path_to_module


@dataclass
class CallFrame:
    """Parsed stack trace frame."""
    file_path: str
    line_number: int
    function_name: str
    class_name: str | None = None


class RCAService:
    """Root cause analysis from error traces."""

    def __init__(
        self,
        index_dir: str | None = None,
        sqlite: SQLiteStore | None = None,
        graph: GraphStore | None = None,
    ):
        from repomind.utils.config import load_config
        if index_dir is None:
            index_dir = load_config().index_dir
        self.sqlite = sqlite or SQLiteStore(str(Path(index_dir) / "index.db"))
        self.graph = graph or GraphStore()
        if graph is None:
            graph_path = Path(index_dir) / "graph.json"
            if graph_path.exists():
                self.graph.load(str(graph_path))

    def analyze_trace(self, trace: str) -> RCAResult:
        """Parse stack trace and find root cause."""
        # Parse stack trace
        frames = self._parse_trace(trace)
        if not frames:
            return RCAResult(
                root_cause="Could not parse stack trace",
                confidence=0.0,
                explanation="No valid call frames found in the trace.",
            )

        # Find the innermost frame (proximate cause)
        proximate = frames[-1]
        error_type, error_msg = self._extract_error_info(trace)

        # Look up symbol in index
        affected_symbols = []
        call_chain = []
        for frame in frames:
            qname = self._frame_to_qname(frame)
            sym = self.sqlite.get_symbol_by_qualified_name(qname)
            if sym:
                affected_symbols.append(SymbolInfo(
                    name=sym.get("name", ""),
                    qualified_name=sym.get("qualified_name", ""),
                    type=safe_symbol_type(sym.get("type", "function")),
                    file_path=sym.get("file_path", ""),
                    start_line=sym.get("start_line", 0),
                    end_line=sym.get("end_line", 0),
                ))
            call_chain.append(f"{frame.file_path}:{frame.line_number} in {frame.function_name}")

        # Build explanation
        explanation = self._build_explanation(error_type, error_msg, proximate, frames)

        return RCAResult(
            root_cause=f"{error_type}: {error_msg}" if error_type else "Unknown error",
            confidence=0.8 if affected_symbols else 0.4,
            affected_symbols=affected_symbols,
            call_chain=call_chain,
            explanation=explanation,
            evidence=[f"Error at {proximate.file_path}:{proximate.line_number}"],
        )

    def _parse_trace(self, trace: str) -> list[CallFrame]:
        """Parse Python stack trace into call frames."""
        frames = []
        # Match "File "path", line N, in func_name"
        pattern = r'File "([^"]+)", line (\d+), in (\w+)'
        for match in re.finditer(pattern, trace):
            file_path = match.group(1)
            line_num = int(match.group(2))
            func_name = match.group(3)
            frames.append(CallFrame(
                file_path=file_path,
                line_number=line_num,
                function_name=func_name,
            ))
        return frames

    def _extract_error_info(self, trace: str) -> tuple[str, str]:
        """Extract error type and message from trace."""
        lines = trace.strip().split("\n")
        last_line = lines[-1].strip() if lines else ""
        match = re.match(r"(\w+(?:\.\w+)*):\s*(.*)", last_line)
        if match:
            return match.group(1), match.group(2)
        return "Error", last_line

    def _frame_to_qname(self, frame: CallFrame) -> str:
        """Convert a stack frame to a qualified name for lookup."""
        module = path_to_module(frame.file_path)
        if frame.class_name:
            return f"{module}.{frame.class_name}.{frame.function_name}"
        return f"{module}.{frame.function_name}"

    def _build_explanation(self, error_type: str, error_msg: str, proximate: CallFrame, frames: list[CallFrame]) -> str:
        parts = [
            f"Error: {error_type}: {error_msg}",
            f"Proximate cause: {proximate.function_name} at {proximate.file_path}:{proximate.line_number}",
            f"Call depth: {len(frames)} frames",
        ]
        if len(frames) > 1:
            parts.append(f"Entry point: {frames[0].function_name} at {frames[0].file_path}:{frames[0].line_number}")
        return "\n".join(parts)
