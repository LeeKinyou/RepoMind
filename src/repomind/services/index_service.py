"""Index service - orchestrates parsing, type inference, and storage."""
from __future__ import annotations

import time
from pathlib import Path

from repomind.models.schemas import IndexOptions, IndexResult, FileInfo
from repomind.core.parser.tree_sitter_parser import TreeSitterParser
from repomind.core.type_inference.inference_engine import TypeInferenceEngine
from repomind.core.call_graph.graph_builder import CallGraphBuilder
from repomind.core.call_graph.resolver import SymbolResolver
from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore


class IndexService:
    """Orchestrates code indexing: parse -> infer -> build graph -> store."""

    def __init__(self, index_dir: str = ".repomind"):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.parser = TreeSitterParser()
        self.type_engine = TypeInferenceEngine()
        self.sqlite = SQLiteStore(str(self.index_dir / "index.db"))
        self.graph = GraphStore()
        self.call_graph_builder = CallGraphBuilder(self.graph)

    def index_directory(self, path: str, options: IndexOptions | None = None) -> IndexResult:
        """Index all Python files in a directory."""
        options = options or IndexOptions()
        start_time = time.time()
        project_path = Path(path).resolve()
        errors: list[str] = []

        if not project_path.exists():
            return IndexResult(success=False, errors=[f"Path not found: {path}"])

        # Collect Python files
        py_files = self._collect_files(project_path, options)
        total_files = len(py_files)

        # Parse all files
        parsed_files = []
        skipped = 0
        for fp in py_files:
            try:
                pf = self.parser.parse_file(str(fp))
                parsed_files.append(pf)
            except Exception as e:
                errors.append(f"Failed to parse {fp}: {e}")
                skipped += 1

        # Store files and symbols
        total_symbols = 0
        total_classes = 0
        total_functions = 0
        for pf in parsed_files:
            try:
                try:
                    rel_path = str(Path(pf.path).relative_to(project_path))
                except ValueError:
                    rel_path = Path(pf.path).name
                file_info = FileInfo(
                    path=rel_path,
                    language="python",
                    hash=self._hash_file(pf.source),
                    line_count=pf.source.count(b"\n") + 1,
                    size_bytes=len(pf.source),
                )
                file_id = self.sqlite.upsert_file(file_info)

                for sym in pf.symbols:
                    sym_id = self.sqlite.insert_symbol(sym, file_id)
                    # Type inference
                    source = pf.source.decode("utf-8", errors="replace")
                    inferred = self.type_engine.infer_symbol(sym, source)
                    if inferred.type_name:
                        self.sqlite.insert_type_info(
                            symbol_id=sym_id,
                            parameter_name=None,
                            inferred_type=inferred.type_name,
                            confidence=inferred.confidence,
                            strategy=inferred.strategy,
                        )
                    total_symbols += 1
                    if sym.type.value == "class":
                        total_classes += 1
                    else:
                        total_functions += 1

                for imp in pf.imports:
                    self.sqlite.insert_import(
                        file_id=file_id,
                        module_path=imp.get("module_path", ""),
                        imported_name=imp.get("imported_name"),
                        alias=imp.get("alias"),
                        is_relative=imp.get("is_relative", False),
                        relative_level=imp.get("relative_level", 0),
                        line_number=imp.get("line_number"),
                    )
            except Exception as e:
                errors.append(f"Failed to store {pf.path}: {e}")

        # Build call graph
        self.call_graph_builder.build(parsed_files)

        # Build symbol index for callee resolution
        symbol_index: dict[str, list[str]] = {}
        for pf in parsed_files:
            for sym in pf.symbols:
                symbol_index.setdefault(sym.name, []).append(sym.qualified_name)

        # Store call relations in SQLite
        total_calls = 0
        total_imports = sum(len(pf.imports) for pf in parsed_files)
        for pf in parsed_files:
            for call in pf.calls:
                caller_qname = SymbolResolver.resolve_caller(call, pf.path)
                callee_qname = SymbolResolver.resolve_callee(call, call.get("caller_class"), symbol_index)
                if caller_qname and callee_qname:
                    self.sqlite.insert_call(
                        caller_qname, callee_qname,
                        call.get("call_type", "direct"),
                        call.get("line_number"),
                    )
                    total_calls += 1

        # Store inheritance
        for pf in parsed_files:
            for cls in pf.classes:
                for parent in cls.get("parents", []):
                    self.sqlite.insert_inherit(cls["qualified_name"], parent)

        # Persist the call graph to disk
        self.graph.save(str(self.index_dir / "graph.json"))

        elapsed = time.time() - start_time
        indexed = total_files - skipped

        return IndexResult(
            success=True,
            total_files=total_files,
            indexed_files=indexed,
            skipped_files=skipped,
            total_symbols=total_symbols,
            total_classes=total_classes,
            total_functions=total_functions,
            total_imports=total_imports,
            total_calls=total_calls,
            elapsed_seconds=round(elapsed, 2),
            index_path=str(self.index_dir),
            errors=errors,
        )

    def get_stats(self) -> dict:
        """Get index statistics."""
        return self.sqlite.get_stats()

    def clear(self) -> None:
        """Clear all index data."""
        self.sqlite.clear()
        self.graph.clear()
        graph_path = self.index_dir / "graph.json"
        if graph_path.exists():
            graph_path.unlink()

    def _collect_files(self, root: Path, options: IndexOptions) -> list[Path]:
        """Collect all Python files, respecting ignore patterns."""
        from pathlib import PurePosixPath
        files = []
        for fp in root.rglob("*.py"):
            rel = fp.relative_to(root)
            rel_posix = PurePosixPath(rel.as_posix())
            # Check each ignore pattern using pathlib match (supports **)
            if any(rel_posix.match(pat) or rel.as_posix().startswith(pat.rstrip("/*").rstrip("*"))
                   for pat in options.ignore_patterns):
                continue
            # Also skip common directories by name
            parts = set(rel.parts)
            if parts & {".venv", "venv", "__pycache__", ".git", "node_modules", ".repomind", ".mypy_cache", ".pytest_cache", ".ruff_cache"}:
                continue
            try:
                if fp.stat().st_size > options.max_file_size_mb * 1024 * 1024:
                    continue
            except OSError:
                continue
                continue
            files.append(fp)
        return sorted(files)

    def _hash_file(self, content: bytes) -> str:
        import hashlib
        return hashlib.sha256(content).hexdigest()[:16]

