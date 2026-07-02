"""Index service - orchestrates parsing, type inference, and storage."""

from __future__ import annotations

import time
from pathlib import Path

from repomind.models.schemas import (
    FileInfo,
    FreshnessReport,
    FreshnessStatus,
    IndexSnapshot,
    IndexOptions,
    IndexResult,
)
from repomind.indexer.ast_parser import TreeSitterParser, ParsedFile
from repomind.indexer.inference_engine import TypeInferenceEngine
from repomind.graph.call_graph_builder import CallGraphBuilder
from repomind.graph.resolver import SymbolResolver
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
                    symbols = self.sqlite.get_symbols_by_file_id(db_file["id"])
                    symbol_qnames = [s["qualified_name"] for s in symbols]
                    for qname in symbol_qnames:
                        if qname in self.graph.graph:
                            self.graph.graph.remove_node(qname)
                    # Delete from SQLite
                    self.sqlite.delete_file(db_file["id"])
        except Exception as e:
            errors.append(f"Failed to clean up deleted files: {e}")

        # 3. Parse files
        parsed_files, skipped = self._parse_files(py_files, project_path, errors)
        try:
            self.sqlite.set_stat("parse_errors", skipped)
        except Exception:
            pass

        # 4. Store files and symbols (includes type inference and idempotency check)
        total_symbols, total_classes, total_functions, symbols_to_embed = (
            self._store_symbols_and_metadata(parsed_files, project_path, errors)
        )

        # 5. Generate and store embeddings for new/updated symbols
        if symbols_to_embed:
            self._generate_embeddings(symbols_to_embed, errors)

        # 6. Build and store call graph (clears calls first)
        total_calls = self._build_and_store_call_graph(parsed_files, errors)

        # 7. Store inheritance relations (clears inherits first)
        self._store_inheritance(parsed_files, errors)

        # 8. Persist call graph
        try:
            self.graph.save(str(self.index_dir / "graph.json"))
        except Exception as e:
            errors.append(f"Failed to save call graph: {e}")

        self._advance_index_version()

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
        from repomind.indexer.ast_symbol_indexer import ASTSymbolIndexer
        ast_indexer = ASTSymbolIndexer()
        for fp in py_files:
            try:
                pf = self.parser.parse_file(str(fp), project_root=str(project_path))
                try:
                    source_code = fp.read_text(encoding="utf-8", errors="replace")
                    ast_symbols = ast_indexer.extract_symbols(source_code, str(fp), project_root=str(project_path))
                    if ast_symbols:
                        pf.symbols = ast_symbols
                except Exception as ae:
                    errors.append(f"AST extraction failed for {fp}: {ae}")
                parsed_files.append(pf)
            except Exception as e:
                errors.append(f"Failed to parse {fp}: {e}")
                skipped += 1
        return parsed_files, skipped

    def _store_symbols_and_metadata(
        self, parsed_files: list[ParsedFile], project_path: Path, errors: list[str]
    ) -> tuple[int, int, int, list[tuple[int, str]]]:
        total_symbols = 0
        total_classes = 0
        total_functions = 0
        symbols_to_embed = []
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
                    text_for_embedding = f"{sym.name} {sym.qualified_name} {sym.docstring or ''}"
                    symbols_to_embed.append((sym_id, text_for_embedding))
                    
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
        return total_symbols, total_classes, total_functions, symbols_to_embed

    def _generate_embeddings(self, new_symbols: list[tuple[int, str]], errors: list[str]) -> None:
        if not new_symbols:
            return
        try:
            from repomind.utils.config import load_config
            import litellm
            
            config = load_config()
            model = config.llm.embedding_model
            if not model:
                return
            
            api_key = config.llm.api_key or None
            api_base = config.llm.base_url or None
            
            inputs = [text for _, text in new_symbols]
            batch_size = 100
            
            for i in range(0, len(inputs), batch_size):
                batch_inputs = inputs[i:i+batch_size]
                batch_ids = [sid for sid, _ in new_symbols[i:i+batch_size]]
                
                try:
                    response = litellm.embedding(
                        model=model,
                        input=batch_inputs,
                        api_key=api_key,
                        api_base=api_base
                    )
                    
                    if i == 0 and response.data:
                        dim = len(response.data[0]["embedding"])
                        self.sqlite.init_vector_table(dim)
                    
                    for j, data in enumerate(response.data):
                        self.sqlite.insert_embedding(batch_ids[j], data["embedding"])
                except Exception as e:
                    errors.append(f"Embedding batch failed: {e}")
        except Exception as e:
            errors.append(f"Failed to generate embeddings: {e}")

    def _build_and_store_call_graph(
        self, parsed_files: list[ParsedFile], errors: list[str]
    ) -> int:
        total_calls = 0
        unresolved_calls = 0
        try:
            # Clear old calls in SQLite to avoid duplication
            self.sqlite.delete_all_calls()

            # Rebuild graph store completely
            self.graph.clear()
            self.call_graph_builder.build(parsed_files)

            symbol_index = self.call_graph_builder.symbol_index

            for pf in parsed_files:
                for call in pf.calls:
                    caller_qname = SymbolResolver.resolve_caller(call, pf.path)
                    callee_result = SymbolResolver.resolve_callee(
                        call, call.get("caller_class"), symbol_index
                    )

                    inserted = False
                    if caller_qname and callee_result:
                        callee_qname_str, resolve_strategy, resolve_confidence = callee_result
                        call_type = call.get("call_type", "direct")
                        confidence = resolve_confidence

                        target_name = call.get("target", "")
                        if target_name.startswith("self."):
                            call_type = "self_call"
                            confidence = 0.95
                        elif caller_qname.split(".")[0] == callee_qname_str.split(".")[0]:
                            call_type = "same_module"
                            confidence = max(0.85, resolve_confidence)
                        else:
                            call_type = resolve_strategy
                            confidence = resolve_confidence

                        inserted = self.sqlite.insert_call(
                            caller_qname,
                            callee_qname_str,
                            call_type,
                            call.get("line_number"),
                            confidence=confidence,
                        )

                    if inserted:
                        total_calls += 1
                    else:
                        unresolved_calls += 1

            self.sqlite.set_stat("resolved_calls", total_calls)
            self.sqlite.set_stat("unresolved_calls", unresolved_calls)
        except Exception as e:
            errors.append(f"Failed to build call graph: {e}")
        return total_calls

    def _store_inheritance(
        self, parsed_files: list[ParsedFile], errors: list[str]
    ) -> None:
        try:
            self.sqlite.delete_all_inherits()
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

    def get_index_version(self) -> int:
        """Return the current persisted index snapshot version."""
        return self.sqlite.get_stat("index_version", 0)

    def check_freshness(
        self, path: str, options: IndexOptions | None = None
    ) -> FreshnessReport:
        """Compare current workspace files with hashes persisted in the index."""
        options = options or IndexOptions()
        project_path = Path(path).resolve()
        errors: list[str] = []

        if not project_path.exists():
            return FreshnessReport(
                status=FreshnessStatus.STALE,
                index_version=self.get_index_version(),
                errors=[f"Path not found: {path}"],
            )

        py_files = self._collect_files(project_path, options)
        current_hashes: dict[str, str] = {}

        for fp in py_files:
            try:
                rel_path = str(fp.relative_to(project_path).as_posix())
                current_hashes[rel_path] = self._hash_file(fp.read_bytes())
            except Exception as e:
                errors.append(f"Failed to hash {fp}: {e}")

        indexed_hashes = {
            str(Path(row["path"]).as_posix()): row["hash"]
            for row in self.sqlite.get_all_files()
        }

        current_paths = set(current_hashes)
        indexed_paths = set(indexed_hashes)
        new_files = sorted(current_paths - indexed_paths)
        deleted_files = sorted(indexed_paths - current_paths)
        changed_files = sorted(
            path
            for path in current_paths & indexed_paths
            if current_hashes[path] != indexed_hashes[path]
        )
        unchanged_files = sorted(
            path
            for path in current_paths & indexed_paths
            if current_hashes[path] == indexed_hashes[path]
        )
        status = (
            FreshnessStatus.STALE
            if errors or new_files or deleted_files or changed_files
            else FreshnessStatus.CURRENT
        )

        return FreshnessReport(
            status=status,
            index_version=self.get_index_version(),
            checked_files=len(current_hashes),
            unchanged_files=unchanged_files,
            changed_files=changed_files,
            new_files=new_files,
            deleted_files=deleted_files,
            errors=errors,
        )

    def refresh_if_stale(
        self, path: str, options: IndexOptions | None = None
    ) -> IndexResult | None:
        """Run an incremental refresh only when the workspace/index snapshot is stale."""
        options = options or IndexOptions()
        freshness = self.check_freshness(path, options)
        if freshness.status == FreshnessStatus.CURRENT:
            return None

        refresh_options = options.model_copy(update={"incremental": True})
        return self.index_directory(path, refresh_options)

    def get_snapshot(
        self,
        file_paths: list[str] | None = None,
        freshness_status: FreshnessStatus = FreshnessStatus.CURRENT,
        errors: list[str] | None = None,
    ) -> IndexSnapshot:
        """Build index snapshot metadata for reports and query results."""
        wanted = {Path(p).as_posix() for p in file_paths or [] if p}
        file_hashes = {}
        for row in self.sqlite.get_all_files():
            rel_path = Path(row["path"]).as_posix()
            if not wanted or rel_path in wanted:
                file_hashes[rel_path] = row["hash"]
        return IndexSnapshot(
            index_version=self.get_index_version(),
            freshness_status=freshness_status,
            file_hashes=file_hashes,
            errors=errors or [],
        )

    def changed_files_since(self, path: str) -> list[str]:
        """Return git working-tree changed Python files when the path is a git repo."""
        import subprocess

        project_path = Path(path).resolve()
        try:
            result = subprocess.run(
                ["git", "-C", str(project_path), "status", "--porcelain"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except Exception:
            return []

        if result.returncode != 0:
            return []

        changed = []
        for line in result.stdout.splitlines():
            if not line or len(line) < 4:
                continue
            rel = line[3:].strip()
            if " -> " in rel:
                rel = rel.split(" -> ", 1)[1].strip()
            rel = rel.replace("\\", "/")
            if rel.endswith(".py"):
                changed.append(rel)
        return sorted(set(changed))

    def validate_file_hashes(
        self, path: str, expected_hashes: dict[str, str]
    ) -> FreshnessReport:
        """Validate report-bound file hashes against the current workspace."""
        project_path = Path(path).resolve()
        changed_files = []
        deleted_files = []
        errors = []

        for rel_path, expected_hash in expected_hashes.items():
            normalized = Path(rel_path).as_posix()
            file_path = project_path / normalized
            if not file_path.exists():
                deleted_files.append(normalized)
                continue
            try:
                current_hash = self._hash_file(file_path.read_bytes())
            except Exception as e:
                errors.append(f"Failed to hash {normalized}: {e}")
                continue
            if current_hash != expected_hash:
                changed_files.append(normalized)

        status = (
            FreshnessStatus.STALE
            if changed_files or deleted_files or errors
            else FreshnessStatus.CURRENT
        )
        return FreshnessReport(
            status=status,
            index_version=self.get_index_version(),
            checked_files=len(expected_hashes),
            changed_files=sorted(changed_files),
            deleted_files=sorted(deleted_files),
            errors=errors,
        )

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
                ".uv-cache",
                ".gemini",
                ".worktrees",
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

    def _advance_index_version(self) -> None:
        self.sqlite.set_stat("index_version", self.get_index_version() + 1)
