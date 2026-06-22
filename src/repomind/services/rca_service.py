"""RCA service - root cause analysis from stack traces."""

from __future__ import annotations

import re
import re
import logging
import litellm
from dataclasses import dataclass
from pathlib import Path
from repomind.utils.config import load_config

logger = logging.getLogger(__name__)

from repomind.models.schemas import (
    RCAResult,
    SymbolInfo,
    safe_symbol_type,
    EvidenceItem,
)
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
        from repomind.utils.errors import GraphLoadError
        if index_dir is None:
            index_dir = load_config().index_dir
        self.index_dir = index_dir
        self.project_root = Path(index_dir).resolve().parent
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

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path from traceback into a project-relative posix path."""
        # Convert backslashes to forward slashes
        path_str = file_path.replace("\\", "/")

        # If absolute path, try to make it relative to the project root
        proj_root_posix = self.project_root.as_posix().lower()
        if path_str.lower().startswith(proj_root_posix):
            rel = path_str[len(proj_root_posix) :].lstrip("/")
            return rel

        # If it contains "/src/" or "/tests/", extract from that point onwards
        for marker in ["/src/", "/tests/"]:
            if marker in path_str:
                idx = path_str.rfind(marker)
                return path_str[idx + 1 :]

        # Or look for exact filename in the indexed files (using SQLite database)
        filename = Path(path_str).name
        if filename:
            try:
                # Query SQLite files table to see if we have files matching this suffix or name
                rows = self.sqlite.search_files_by_suffix(filename)
                if rows:
                        # Return the shortest match or first match
                        for row in rows:
                            p = row["path"]
                            # Verify the suffix matches
                            if p.replace("\\", "/").endswith(filename):
                                return p.replace("\\", "/")
            except Exception:
                pass

        # Fallback: return file_path with normalized slashes
        return path_str

    def _get_code_snippet(
        self, file_path: str, line_number: int, context_lines: int = 5
    ) -> str | None:
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project_root / path
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

        # Build structured evidences list
        evidences = []
        for idx, frame in enumerate(frames):
            snippet = self._get_code_snippet(frame.file_path, frame.line_number)
            if snippet:
                evidences.append(
                    EvidenceItem(
                        file_path=frame.file_path,
                        symbol=frame.function_name,
                        start_line=max(1, frame.line_number - 5),
                        end_line=frame.line_number + 5,
                        snippet=snippet,
                        source="traceback",
                        why_relevant=f"Frame #{idx + 1} in stack trace executing function '{frame.function_name}' at line {frame.line_number}",
                    )
                )

        for sym in affected_symbols:
            if any(
                ev.file_path == sym.file_path and ev.symbol == sym.name
                for ev in evidences
            ):
                continue
            sym_snippet = ""
            try:
                p = Path(sym.file_path)
                if not p.is_absolute():
                    p = self.project_root / p
                if p.exists():
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                    start_idx = max(0, sym.start_line - 1)
                    end_idx = min(len(lines), sym.end_line)
                    sym_snippet = "\n".join(lines[start_idx:end_idx])
            except Exception:
                pass
            if sym_snippet:
                evidences.append(
                    EvidenceItem(
                        file_path=sym.file_path,
                        symbol=sym.qualified_name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        snippet=sym_snippet,
                        source="keyword",
                        why_relevant=f"Symbol '{sym.name}' matched during local code retrieval",
                    )
                )

        verification_command = "uv run pytest"
        test_files = [
            ev.file_path for ev in evidences if "test" in ev.file_path.lower()
        ]
        if test_files:
            verification_command = f"uv run pytest {test_files[0]}"

        return RCAResult(
            root_cause=root_cause,
            confidence=0.8 if affected_symbols else 0.4,
            affected_symbols=affected_symbols,
            call_chain=call_chain,
            explanation=explanation,
            suggested_fix=suggested_fix,
            evidence=[f"Error at {proximate.file_path}:{proximate.line_number}"],
            evidences=evidences,
            verification_command=verification_command,
        )

    def _parse_trace(self, trace: str) -> list[CallFrame]:
        """Parse Python stack trace into call frames."""
        frames = []
        # Match "File "path", line N, in func_name"
        pattern = r'File "([^"]+)", line (\d+), in (.+)'
        for match in re.finditer(pattern, trace):
            file_path = match.group(1)
            line_num = int(match.group(2))
            func_name = match.group(3)
            frames.append(
                CallFrame(
                    file_path=self._normalize_path(file_path),
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
