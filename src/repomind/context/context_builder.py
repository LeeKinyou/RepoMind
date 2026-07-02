"""RCA service - root cause analysis from stack traces."""

from __future__ import annotations

import logging
from pathlib import Path

from repomind.models.evidence import Evidence, EvidenceBundle
from repomind.models.schemas import (
    IndexSnapshot,
    RCAResult,
    SymbolInfo,
    safe_symbol_type,
)
from repomind.indexer.file_scanner import IndexService
from repomind.storage.graph_store import GraphStore
from repomind.storage.sqlite_store import SQLiteStore
from repomind.context.pytest_failure import PytestFailureParser
from repomind.context.python_traceback import PythonTracebackParser
from repomind.context.trace_parser import TraceParser
from repomind.utils.config import load_config
from repomind.utils.errors import GraphLoadError
from repomind.utils.path_utils import path_to_module

logger = logging.getLogger(__name__)


class RCAService:
    """Root cause analysis from error traces."""

    def __init__(
        self,
        index_dir: str | None = None,
        sqlite: SQLiteStore | None = None,
        graph: GraphStore | None = None,
        auto_refresh: bool = True,
    ):
        if index_dir is None:
            index_dir = load_config().index_dir
        self.index_dir = index_dir
        self.project_root = Path(index_dir).resolve().parent
        self.auto_refresh = auto_refresh
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
        
        self.parsers: list[TraceParser] = [PythonTracebackParser(), PytestFailureParser()]
        self.index_service = IndexService(
            index_dir=self.index_dir,
            sqlite=self.sqlite,
            graph=self.graph,
        )

    def _ensure_fresh(self) -> IndexSnapshot:
        if self.auto_refresh:
            try:
                self.index_service.refresh_if_stale(str(self.project_root))
            except Exception as e:
                logger.warning("Failed to refresh stale index before RCA: %s", e)
                return self.index_service.get_snapshot(errors=[str(e)])
        return self.index_service.get_snapshot()

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path from traceback into a project-relative posix path."""
        path_str = file_path.replace("\\", "/")

        proj_root_posix = self.project_root.as_posix().lower()
        if path_str.lower().startswith(proj_root_posix):
            rel = path_str[len(proj_root_posix) :].lstrip("/")
            return rel

        for marker in ["/src/", "/tests/"]:
            if marker in path_str:
                idx = path_str.rfind(marker)
                return path_str[idx + 1 :]

        filename = Path(path_str).name
        if filename:
            try:
                rows = self.sqlite.search_files_by_suffix(filename)
                if rows:
                    for row in rows:
                        p = row["path"]
                        if p.replace("\\", "/").endswith(filename):
                            return p.replace("\\", "/")
            except Exception:
                pass

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

    def _frame_to_qname(self, file_path: str, function_name: str) -> str:
        module = path_to_module(file_path)
        return f"{module}.{function_name}"

    def collect_trace_evidence(self, trace: str) -> EvidenceBundle:
        """Parse stack trace and collect evidence deterministically."""
        snapshot = self._ensure_fresh()
        parsed = None
        for parser in self.parsers:
            if parser.can_parse(trace):
                parsed = parser.parse(trace)
                break
        
        if not parsed:
            return EvidenceBundle(
                summary="Could not parse stack trace",
                warnings=["No valid call frames found in the trace."],
                metadata={"snapshot": snapshot.model_dump(mode="json")},
            )

        warnings = list(parsed.warnings)
        if not parsed.frames:
            return EvidenceBundle(
                summary="No valid frames",
                warnings=warnings,
                metadata={"snapshot": snapshot.model_dump(mode="json")},
            )

        proximate_frame = parsed.proximate_frame
        summary = "Unknown Error"
        error_type = "Unknown"
        if parsed.exceptions:
            exc = parsed.exceptions[-1]
            summary = f"{exc.type}: {exc.message}"
            error_type = exc.type

        # Collect active line numbers for each file in the traceback
        active_lines_by_file: dict[str, set[int]] = {}
        for frame in parsed.frames:
            norm_p = self._normalize_path(frame.file_path)
            active_lines_by_file.setdefault(norm_p, set()).add(frame.line_number)

        evidences = []
        affected_symbols = []

        for idx, frame in enumerate(parsed.frames):
            norm_path = self._normalize_path(frame.file_path)
            
            snippet = None
            if norm_path in active_lines_by_file:
                try:
                    p = Path(norm_path)
                    if not p.is_absolute():
                        p = self.project_root / p
                    if p.exists():
                        source_code = p.read_text(encoding="utf-8", errors="replace")
                        from repomind.context.skeletonizer import CodeSkeletonizer
                        skeletonizer = CodeSkeletonizer()
                        raw_skeleton = skeletonizer.skeletonize(source_code, active_lines_by_file[norm_path])
                        
                        # Add dynamic target line marker (e.g. => line_number) to the skeletonized code
                        lines = raw_skeleton.splitlines()
                        for ln in active_lines_by_file[norm_path]:
                            if 0 < ln <= len(lines):
                                lines[ln - 1] = "=> " + lines[ln - 1]
                        snippet = "\n".join(lines)
                except Exception as e:
                    logger.warning("Skeletonization failed for %s: %s", norm_path, e)

            if snippet is None:
                snippet = self._get_code_snippet(norm_path, frame.line_number)
            
            qname = self._frame_to_qname(norm_path, frame.function_name)
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

            evidence_id = f"trace_frame_{idx}"
            evidences.append(
                Evidence(
                    evidence_id=evidence_id,
                    source="trace",
                    file_path=norm_path,
                    symbol=qname if sym else frame.function_name,
                    start_line=max(1, frame.line_number - 5),
                    end_line=frame.line_number + 5,
                    snippet=snippet,
                    relevance_score=1.0,
                    reason=f"Frame #{idx + 1} in stack trace executing function '{frame.function_name}' at line {frame.line_number}",
                )
            )

        evidence_files = sorted({ev.file_path for ev in evidences})
        snapshot = self.index_service.get_snapshot(evidence_files)
        metadata: dict[str, object] = {"snapshot": snapshot.model_dump(mode="json")}
        if error_type:
            metadata["error_type"] = error_type
        if proximate_frame:
            metadata["proximate_cause"] = {
                "file_path": self._normalize_path(proximate_frame.file_path),
                "function_name": proximate_frame.function_name,
                "line_number": proximate_frame.line_number,
            }

        return EvidenceBundle(
            summary=summary,
            evidences=evidences,
            symbols=affected_symbols,
            relations=[],
            warnings=warnings,
            metadata=metadata
        )

    def analyze_trace(self, trace: str) -> RCAResult:
        """Backward compatibility for old RCA service clients."""
        bundle = self.collect_trace_evidence(trace)
        return bundle.to_legacy_result()
