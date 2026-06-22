"""Index service - orchestrates parsing, type inference, and storage."""

from __future__ import annotations

import time
from pathlib import Path

from repomind.models.schemas import IndexOptions, IndexResult, FileInfo
from repomind.core.parser.tree_sitter_parser import TreeSitterParser, ParsedFile
from repomind.core.type_inference.inference_engine import TypeInferenceEngine
from repomind.core.call_graph.graph_builder import CallGraphBuilder
from repomind.core.call_graph.resolver import SymbolResolver
from repomind.storage.sqlite_store import SQLiteStore
from repomind.storage.graph_store import GraphStore


class IndexService:
    """Orchestrates code indexing: parse -> infer -> build graph -> store."""

    def __init__(
        self,
        index_dir: str | None = None,
        parser: TreeSitterParser | None = None,
        type_engine: TypeInferenceEngine | None = None,
        sqlite: SQLiteStore | None = None,
        graph: GraphStore | None = None,
        call_graph_builder: CallGraphBuilder | None = None,
    ):
        from repomind.utils.config import load_config

        if index_dir is None:
            index_dir = load_config().index_dir
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.parser = parser or TreeSitterParser()
        self.type_engine = type_engine or TypeInferenceEngine()
        self.sqlite = sqlite or SQLiteStore(str(self.index_dir / "index.db"))
        self.graph = graph or GraphStore()
        self.call_graph_builder = call_graph_builder or CallGraphBuilder(self.graph)

    def index_directory(
        self, path: str, options: IndexOptions | None = None
    ) -> IndexResult:
        """Index all Python files in a directory."""
        options = options or IndexOptions()
        start_time = time.time()
        project_path = Path(path).resolve()
        errors: list[str] = []

        if not project_path.exists():
            return IndexResult(success=False, errors=[f"Path not found: {path}"])

        # If not incremental, clear existing index first to ensure a clean build
        if not options.incremental:
            self.clear()

        # 1. Collect files
        py_files = self._collect_files(project_path, options)
        total_files = len(py_files)

        # 2. Cleanup deleted files from SQLite and GraphStore
        from pathlib import PurePosixPath

        try:
            db_files = self.sqlite.get_all_files()
            active_rel_paths = {
                str(fp.relative_to(project_path).as_posix()) for fp in py_files
            }

            for db_file in db_files:
                db_path_posix = PurePosixPath(db_file["path"]).as_posix()
                if db_path_posix not in active_rel_paths:
                    # Find symbols in this file to remove from GraphStore
                    with self.sqlite._read_connect() as conn:
                        rows = conn.execute(
                            "SELECT qualified_name FROM symbols WHERE file_id = ?",
                            (db_file["id"],),
                        ).fetchall()
                        symbol_qnames = [r["qualified_name"] for r in rows]
                    for qname in symbol_qnames:
                        if qname in self.graph.graph:
                            self.graph.graph.remove_node(qname)
                    # Delete from SQLite
                    self.sqlite.delete_file(db_file["id"])
        except Exception as e:
            errors.append(f"Failed to clean up deleted files: {e}")

        # 3. Parse files
        parsed_files, skipped = self._parse_files(py_files, project_path, errors)

        # 4. Store files and symbols (includes type inference and idempotency check)
        total_symbols, total_classes, total_functions = (
            self._store_symbols_and_metadata(parsed_files, project_path, errors)
        )

        # 5. Build and store call graph (clears calls first)
        total_calls = self._build_and_store_call_graph(parsed_files, errors)

        # 6. Store inheritance relations (clears inherits first)
        self._store_inheritance(parsed_files, errors)

        # 7. Persist call graph
        try:
            self.graph.save(str(self.index_dir / "graph.json"))
        except Exception as e:
            errors.append(f"Failed to save call graph: {e}")

        elapsed = time.time() - start_time
        indexed = total_files - skipped
        total_imports = sum(len(pf.imports) for pf in parsed_files)

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

    def _parse_files(
        self, py_files: list[Path], project_path: Path, errors: list[str]
    ) -> tuple[list[ParsedFile], int]:
        parsed_files = []
        skipped = 0
        for fp in py_files:
            try:
                pf = self.parser.parse_file(str(fp), project_root=str(project_path))
                parsed_files.append(pf)
            except Exception as e:
                errors.append(f"Failed to parse {fp}: {e}")
                skipped += 1
        return parsed_files, skipped

    def _store_symbols_and_metadata(
        self, parsed_files: list[ParsedFile], project_path: Path, errors: list[str]
    ) -> tuple[int, int, int]:
        total_symbols = 0
        total_classes = 0
        total_functions = 0
        from repomind.models.schemas import SymbolType

        for pf in parsed_files:
            try:
                try:
                    rel_path = str(Path(pf.path).relative_to(project_path).as_posix())
                except ValueError:
                    rel_path = Path(pf.path).name
                file_info = FileInfo(
                    path=rel_path,
                    language="python",
                    hash=self._hash_file(pf.source),
                    line_count=pf.source.count(b"\n") + 1,
                    size_bytes=len(pf.source),
                )

                # Check if hash has changed (idempotency check)
                existing = self.sqlite.get_file_by_path(rel_path)
                if existing and existing["hash"] == file_info.hash:
                    # Just count symbols for stats and skip DB inserts
                    total_symbols += len(pf.symbols)
                    for sym in pf.symbols:
                        if sym.type == SymbolType.CLASS:
                            total_classes += 1
                        else:
                            total_functions += 1
                    continue

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
                    if sym.type == SymbolType.CLASS:
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
        return total_symbols, total_classes, total_functions

    def _build_and_store_call_graph(
        self, parsed_files: list[ParsedFile], errors: list[str]
    ) -> int:
        total_calls = 0
        try:
            # Clear old calls in SQLite to avoid duplication
            with self.sqlite._connect() as conn:
                conn.execute("DELETE FROM calls")

            # Rebuild graph store completely
            self.graph.clear()
            self.call_graph_builder.build(parsed_files)

            symbol_index: dict[str, list[str]] = {}
            for pf in parsed_files:
                for sym in pf.symbols:
                    symbol_index.setdefault(sym.name, []).append(sym.qualified_name)

            for pf in parsed_files:
                for call in pf.calls:
                    caller_qname = SymbolResolver.resolve_caller(call, pf.path)
                    callee_qname = SymbolResolver.resolve_callee(
                        call, call.get("caller_class"), symbol_index
                    )
                    if caller_qname and callee_qname:
                        self.sqlite.insert_call(
                            caller_qname,
                            callee_qname,
                            call.get("call_type", "direct"),
                            call.get("line_number"),
                        )
                        total_calls += 1
        except Exception as e:
            errors.append(f"Failed to build call graph: {e}")
        return total_calls

    def _store_inheritance(
        self, parsed_files: list[ParsedFile], errors: list[str]
    ) -> None:
        try:
            with self.sqlite._connect() as conn:
                conn.execute("DELETE FROM inherits")
        except Exception as e:
            errors.append(f"Failed to clear old inheritance relations: {e}")

        for pf in parsed_files:
            for cls in pf.classes:
                for parent in cls.get("parents", []):
                    try:
                        self.sqlite.insert_inherit(cls["qualified_name"], parent)
                    except Exception as e:
                        errors.append(
                            f"Failed to store inheritance for {cls['qualified_name']}: {e}"
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
            if any(
                rel_posix.match(pat)
                or rel.as_posix().startswith(pat.rstrip("/*").rstrip("*"))
                for pat in options.ignore_patterns
            ):
                continue
            # Also skip common directories by name
            parts = set(rel.parts)
            if parts & {
                ".venv",
                "venv",
                "__pycache__",
                ".git",
                "node_modules",
                ".repomind",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
            }:
                continue
            try:
                if fp.stat().st_size > options.max_file_size_mb * 1024 * 1024:
                    continue
            except OSError:
                continue
            files.append(fp)
        return sorted(files)

    def _hash_file(self, content: bytes) -> str:
        import hashlib

        return hashlib.sha256(content).hexdigest()[:16]
