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
        import logging
        from repomind.utils.config import load_config
        from repomind.utils.errors import GraphLoadError

        logger = logging.getLogger(__name__)
        if index_dir is None:
            index_dir = load_config().index_dir
        self.sqlite = sqlite or SQLiteStore(str(Path(index_dir) / "index.db"))
        self.graph = graph or GraphStore()
        if graph is None:
            graph_path = Path(index_dir) / "graph.json"
            if graph_path.exists():
                try:
                    self.graph.load(str(graph_path))
                except GraphLoadError as e:
                    logger.warning(
                        "Failed to load graph: %s. Starting with empty graph.", e
                    )

    def _get_code_snippet(
        self, file_path: str, line_number: int, context_lines: int = 5
    ) -> str | None:
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(0, line_number - 1 - context_lines)
            end = min(len(lines), line_number + context_lines)
            snippet_lines = []
            for i in range(start, end):
                prefix = "=> " if i == line_number - 1 else "   "
                snippet_lines.append(f"{prefix}{i + 1}: {lines[i]}")
            return "\n".join(snippet_lines)
        except Exception:
            return None

    def analyze_trace(self, trace: str) -> RCAResult:
        """Parse stack trace and find root cause."""
        import logging
        import litellm
        from repomind.utils.config import load_config

        logger = logging.getLogger(__name__)

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
                affected_symbols.append(
                    SymbolInfo(
                        name=sym.get("name", ""),
                        qualified_name=sym.get("qualified_name", ""),
                        type=safe_symbol_type(sym.get("type", "function")),
                        file_path=sym.get("file_path", ""),
                        start_line=sym.get("start_line", 0),
                        end_line=sym.get("end_line", 0),
                    )
                )
            call_chain.append(
                f"{frame.file_path}:{frame.line_number} in {frame.function_name}"
            )

        # Extract source code snippets from trace frames
        source_code_text_parts = []
        for frame in frames:
            snippet = self._get_code_snippet(frame.file_path, frame.line_number)
            if snippet:
                source_code_text_parts.append(
                    f"File: {frame.file_path}, Line: {frame.line_number} in {frame.function_name}\n"
                    f"```python\n{snippet}\n```"
                )
        source_code_text = (
            "\n\n".join(source_code_text_parts)
            if source_code_text_parts
            else "[Source code not available]"
        )

        # Graph expansion (2 hops) from proximate cause symbol
        graph_text_parts = []
        proximate_qname = self._frame_to_qname(proximate)
        if proximate_qname:
            expanded = self.graph.bfs_expand(proximate_qname, hops=2)
            for eq in expanded:
                sym = self.sqlite.get_symbol_by_qualified_name(eq)
                if sym:
                    sig = sym.get("signature") or ""
                    doc = sym.get("docstring") or ""
                    graph_text_parts.append(
                        f"- Symbol: `{eq}` ({sym.get('type')})\n"
                        f"  Signature: `{sig}`\n"
                        f"  Docstring: {doc}"
                    )
        call_graph_text = (
            "\n".join(graph_text_parts)
            if graph_text_parts
            else "[No call graph context available]"
        )

        # Call LiteLLM for RCA
        config = load_config()
        model_name = config.llm.model or "claude-sonnet-4-6"

        prompt = (
            f"You are a Root Cause Analysis (RCA) Assistant. Analyze the following Python stack trace, "
            f"the proximate source code context from the referenced files, and call graph relationship contexts "
            f"to determine the root cause of the error.\n\n"
            f"Error Trace:\n{trace}\n\n"
            f"Source Code Frame context:\n{source_code_text}\n\n"
            f"Call Graph dependencies:\n{call_graph_text}\n\n"
            f"Please structure your output using exactly the tags below:\n"
            f"[ROOT_CAUSE] A short one-line description of the root cause.\n"
            f"[EXPLANATION] A detailed explanation of why the error occurred, step-by-step.\n"
            f"[SUGGESTED_FIX] A specific, actionable code fix or instructions to fix this error.\n"
        )

        litellm_args = {}
        if config.llm.api_key:
            litellm_args["api_key"] = config.llm.api_key
        if config.llm.base_url:
            litellm_args["base_url"] = config.llm.base_url

        root_cause = f"{error_type}: {error_msg}" if error_type else "Unknown error"
        explanation = self._build_explanation(error_type, error_msg, proximate, frames)
        suggested_fix = None

        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                timeout=30,
                **litellm_args,
            )
            response_content = response.choices[0].message.content
            if "[ROOT_CAUSE]" in response_content:
                parts = response_content.split("[ROOT_CAUSE]")
                subparts = parts[1].split("[EXPLANATION]")
                root_cause = subparts[0].strip()
                if len(subparts) > 1:
                    subparts2 = subparts[1].split("[SUGGESTED_FIX]")
                    explanation = subparts2[0].strip()
                    if len(subparts2) > 1:
                        suggested_fix = subparts2[1].strip()
            else:
                explanation = response_content
        except Exception as e:
            logger.warning(
                "LiteLLM completion failed for RCA: %s. Falling back to deterministic analysis.",
                e,
            )

        return RCAResult(
            root_cause=root_cause,
            confidence=0.8 if affected_symbols else 0.4,
            affected_symbols=affected_symbols,
            call_chain=call_chain,
            explanation=explanation,
            suggested_fix=suggested_fix,
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
            frames.append(
                CallFrame(
                    file_path=file_path,
                    line_number=line_num,
                    function_name=func_name,
                )
            )
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

    def _build_explanation(
        self,
        error_type: str,
        error_msg: str,
        proximate: CallFrame,
        frames: list[CallFrame],
    ) -> str:
        parts = [
            f"Error: {error_type}: {error_msg}",
            f"Proximate cause: {proximate.function_name} at {proximate.file_path}:{proximate.line_number}",
            f"Call depth: {len(frames)} frames",
        ]
        if len(frames) > 1:
            parts.append(
                f"Entry point: {frames[0].function_name} at {frames[0].file_path}:{frames[0].line_number}"
            )
        return "\n".join(parts)
