"""SQLite structured storage for RepoMind."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from repomind.models.schemas import (
    SymbolInfo,
    FileInfo,
)


# SQL DDL
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    path            TEXT    NOT NULL UNIQUE,
    hash            TEXT    NOT NULL,
    language        TEXT    NOT NULL,
    line_count      INTEGER NOT NULL DEFAULT 0,
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symbols (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    type            TEXT    NOT NULL,
    qualified_name  TEXT    NOT NULL,
    start_line      INTEGER NOT NULL,
    end_line        INTEGER NOT NULL,
    docstring       TEXT,
    signature       TEXT,
    is_exported     BOOLEAN NOT NULL DEFAULT TRUE,
    parent_class_id INTEGER REFERENCES symbols(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS type_info (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id           INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    parameter_name      TEXT,
    type_annotation     TEXT,
    inferred_type       TEXT,
    confidence          REAL    NOT NULL DEFAULT 0,
    inference_strategy  TEXT    NOT NULL,
    evidence            TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    module_path     TEXT    NOT NULL,
    imported_name   TEXT,
    alias           TEXT,
    is_relative     BOOLEAN NOT NULL DEFAULT FALSE,
    relative_level  INTEGER NOT NULL DEFAULT 0,
    line_number     INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_id       INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    callee_id       INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    call_type       TEXT    NOT NULL,
    confidence      REAL    NOT NULL DEFAULT 1.0,
    line_number     INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inherits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    parent_id       INTEGER REFERENCES symbols(id),
    parent_name     TEXT    NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type);
CREATE INDEX IF NOT EXISTS idx_symbols_parent_class ON symbols(parent_class_id);
CREATE INDEX IF NOT EXISTS idx_type_info_symbol ON type_info(symbol_id);
CREATE INDEX IF NOT EXISTS idx_type_info_strategy ON type_info(inference_strategy);
CREATE INDEX IF NOT EXISTS idx_type_info_confidence ON type_info(confidence);
CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_id);
CREATE INDEX IF NOT EXISTS idx_imports_module ON imports(module_path);
CREATE INDEX IF NOT EXISTS idx_imports_name ON imports(imported_name);
CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_id);
CREATE INDEX IF NOT EXISTS idx_calls_type ON calls(call_type);
CREATE INDEX IF NOT EXISTS idx_calls_confidence ON calls(confidence);
CREATE INDEX IF NOT EXISTS idx_inherits_child ON inherits(child_id);
CREATE INDEX IF NOT EXISTS idx_inherits_parent ON inherits(parent_id);
CREATE INDEX IF NOT EXISTS idx_inherits_parent_name ON inherits(parent_name);

CREATE TABLE IF NOT EXISTS indexing_stats (
    key             TEXT    PRIMARY KEY,
    value           INTEGER NOT NULL
);
"""


class SQLiteStore:
    """SQLite-based structured storage for symbols, relations, and metadata."""

    _CLEARABLE_TABLES = (
        "inherits",
        "calls",
        "imports",
        "type_info",
        "symbols",
        "files",
        "indexing_stats",
    )

    def __init__(self, db_path: str = ".repomind/index.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self.vector_available = False
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    def init_vector_table(self, dimension: int) -> bool:
        """Dynamically create the virtual vector table with the specified dimension."""
        if not self.vector_available:
            return False
        with self._connect() as conn:
            # Drop the table if it exists but has a different dimension
            # (sqlite-vec doesn't allow altering vec0 tables easily)
            # To be safe, we'll try to create it. If it fails due to dimension mismatch,
            # we don't handle it gracefully yet, but usually it's cleared on full re-index.
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_symbols USING vec0(symbol_id INTEGER PRIMARY KEY, embedding float[{dimension}]);"
            )
        return True

    def set_stat(self, key: str, value: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO indexing_stats (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_stat(self, key: str, default: int = 0) -> int:
        with self._read_connect() as conn:
            table_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='indexing_stats'"
            ).fetchone()
            if not table_exists:
                return default
            row = conn.execute(
                "SELECT value FROM indexing_stats WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a reusable database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            try:
                import sqlite_vec
            except ImportError:
                self.vector_available = False
            else:
                self._conn.enable_load_extension(True)
                try:
                    sqlite_vec.load(self._conn)
                    self.vector_available = True
                finally:
                    self._conn.enable_load_extension(False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def _read_connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._get_conn()
        yield conn

    # === File operations ===

    def upsert_file(self, file_info: FileInfo) -> int:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, hash FROM files WHERE path = ?", (file_info.path,)
            ).fetchone()
            if existing:
                if existing["hash"] == file_info.hash:
                    return existing["id"]
                # Clean up old records before updating (relying on ON DELETE CASCADE)
                conn.execute("DELETE FROM symbols WHERE file_id = ?", (existing["id"],))
                conn.execute("DELETE FROM imports WHERE file_id = ?", (existing["id"],))
                conn.execute(
                    "UPDATE files SET hash=?, line_count=?, size_bytes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (
                        file_info.hash,
                        file_info.line_count,
                        file_info.size_bytes,
                        existing["id"],
                    ),
                )
                return existing["id"]
            cur = conn.execute(
                "INSERT INTO files (path, hash, language, line_count, size_bytes) VALUES (?, ?, ?, ?, ?)",
                (
                    file_info.path,
                    file_info.hash,
                    file_info.language,
                    file_info.line_count,
                    file_info.size_bytes,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError("INSERT did not return a row ID")
            return cur.lastrowid

    def get_file_by_path(self, path: str) -> dict | None:
        with self._read_connect() as conn:
            row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
            return dict(row) if row else None

    def get_all_files(self) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute("SELECT * FROM files").fetchall()
            return [dict(r) for r in rows]

    def delete_file(self, file_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    # === Symbol operations ===

    def insert_symbol(self, symbol: SymbolInfo, file_id: int) -> int:
        with self._connect() as conn:
            parent_id = None
            if symbol.parent_class:
                parent = conn.execute(
                    "SELECT id FROM symbols WHERE qualified_name = ?",
                    (symbol.parent_class,),
                ).fetchone()
                if parent:
                    parent_id = parent["id"]
            cur = conn.execute(
                """INSERT INTO symbols (file_id, name, type, qualified_name, start_line, end_line,
                   docstring, signature, is_exported, parent_class_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    symbol.name,
                    symbol.type.value,
                    symbol.qualified_name,
                    symbol.start_line,
                    symbol.end_line,
                    symbol.docstring,
                    symbol.signature,
                    symbol.is_exported,
                    parent_id,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError("INSERT did not return a row ID")
            return cur.lastrowid

    def get_symbol_by_qualified_name(self, qualified_name: str) -> dict | None:
        with self._read_connect() as conn:
            row = conn.execute(
                """SELECT s.*, f.path AS file_path 
                   FROM symbols s 
                   JOIN files f ON s.file_id = f.id 
                   WHERE s.qualified_name = ?""",
                (qualified_name,),
            ).fetchone()
            return dict(row) if row else None

    def search_symbols(self, query: str, limit: int = 20) -> list[dict]:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._read_connect() as conn:
            rows = conn.execute(
                """SELECT s.*, f.path AS file_path 
                   FROM symbols s 
                   JOIN files f ON s.file_id = f.id 
                   WHERE s.name LIKE ? ESCAPE '\\' OR s.qualified_name LIKE ? ESCAPE '\\' 
                   LIMIT ?""",
                (f"%{escaped}%", f"%{escaped}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_embedding(self, symbol_id: int, embedding: list[float]) -> None:
        """Insert a vector embedding for a symbol."""
        with self._connect() as conn:
            import json

            # Table might not exist if init_vector_table wasn't called yet
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO vec_symbols (symbol_id, embedding) VALUES (?, ?)",
                    (symbol_id, json.dumps(embedding)),
                )
            except sqlite3.OperationalError:
                pass

    def search_vectors(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[dict]:
        """Search for similar symbols using L2 distance."""
        with self._read_connect() as conn:
            import json

            try:
                rows = conn.execute(
                    """
                    SELECT s.*, f.path AS file_path, v.distance
                    FROM vec_symbols v
                    JOIN symbols s ON v.symbol_id = s.id
                    JOIN files f ON s.file_id = f.id
                    WHERE embedding MATCH ? AND k = ?
                    ORDER BY distance
                    """,
                    (json.dumps(query_embedding), limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                # Table might not exist
                return []

    def get_all_symbols(self) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute(
                """SELECT s.*, f.path AS file_path 
                   FROM symbols s 
                   JOIN files f ON s.file_id = f.id"""
            ).fetchall()
            return [dict(r) for r in rows]

    # === Relation operations ===

    def insert_call(
        self,
        caller_qname: str,
        callee_qname: str,
        call_type: str,
        line_number: int | None = None,
        confidence: float = 1.0,
    ) -> bool:
        with self._connect() as conn:
            caller = conn.execute(
                "SELECT id FROM symbols WHERE qualified_name = ?", (caller_qname,)
            ).fetchone()
            callee = conn.execute(
                "SELECT id FROM symbols WHERE qualified_name = ?", (callee_qname,)
            ).fetchone()
            if caller and callee:
                conn.execute(
                    "INSERT INTO calls (caller_id, callee_id, call_type, confidence, line_number) VALUES (?, ?, ?, ?, ?)",
                    (caller["id"], callee["id"], call_type, confidence, line_number),
                )
                return True
            return False

    def insert_import(
        self,
        file_id: int,
        module_path: str,
        imported_name: str | None = None,
        alias: str | None = None,
        is_relative: bool = False,
        relative_level: int = 0,
        line_number: int | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO imports (file_id, module_path, imported_name, alias, is_relative, relative_level, line_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    file_id,
                    module_path,
                    imported_name,
                    alias,
                    is_relative,
                    relative_level,
                    line_number,
                ),
            )

    def insert_inherit(
        self, child_qname: str, parent_name: str, parent_qname: str | None = None
    ) -> None:
        with self._connect() as conn:
            child = conn.execute(
                "SELECT id FROM symbols WHERE qualified_name = ?", (child_qname,)
            ).fetchone()
            parent = None
            if parent_qname:
                parent = conn.execute(
                    "SELECT id FROM symbols WHERE qualified_name = ?", (parent_qname,)
                ).fetchone()
            if child:
                conn.execute(
                    "INSERT INTO inherits (child_id, parent_id, parent_name) VALUES (?, ?, ?)",
                    (child["id"], parent["id"] if parent else None, parent_name),
                )

    def insert_type_info(
        self,
        symbol_id: int,
        parameter_name: str | None,
        inferred_type: str,
        confidence: float,
        strategy: str,
        type_annotation: str | None = None,
        evidence: str | None = None,
    ) -> int:
        """Insert type inference result."""
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO type_info (symbol_id, parameter_name, type_annotation, inferred_type, confidence, inference_strategy, evidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    symbol_id,
                    parameter_name,
                    type_annotation,
                    inferred_type,
                    confidence,
                    strategy,
                    evidence,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError("INSERT did not return a row ID")
            return cur.lastrowid

    def get_callees(self, caller_qname: str) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute(
                """SELECT s.*, f.path AS file_path, c.call_type, c.confidence, c.line_number
                   FROM calls c 
                   JOIN symbols s ON c.callee_id = s.id
                   JOIN files f ON s.file_id = f.id
                   WHERE c.caller_id = (SELECT id FROM symbols WHERE qualified_name = ?)""",
                (caller_qname,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_callers(self, callee_qname: str) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute(
                """SELECT s.*, f.path AS file_path, c.call_type, c.confidence, c.line_number
                   FROM calls c 
                   JOIN symbols s ON c.caller_id = s.id
                   JOIN files f ON s.file_id = f.id
                   WHERE c.callee_id = (SELECT id FROM symbols WHERE qualified_name = ?)""",
                (callee_qname,),
            ).fetchall()
            return [dict(r) for r in rows]

    # === Stats ===

    def get_stats(self) -> dict:
        with self._read_connect() as conn:
            files = conn.execute("SELECT COUNT(*) as cnt FROM files").fetchone()["cnt"]
            symbols = conn.execute("SELECT COUNT(*) as cnt FROM symbols").fetchone()[
                "cnt"
            ]
            classes = conn.execute(
                "SELECT COUNT(*) as cnt FROM symbols WHERE type='class'"
            ).fetchone()["cnt"]
            functions = conn.execute(
                "SELECT COUNT(*) as cnt FROM symbols WHERE type IN ('function','method')"
            ).fetchone()["cnt"]
            imports = conn.execute("SELECT COUNT(*) as cnt FROM imports").fetchone()[
                "cnt"
            ]
            calls = conn.execute("SELECT COUNT(*) as cnt FROM calls").fetchone()["cnt"]

            resolved_calls = self.get_stat("resolved_calls", calls)
            unresolved_calls = self.get_stat("unresolved_calls", 0)
            total = resolved_calls + unresolved_calls
            resolution_rate = (resolved_calls / total) if total > 0 else 1.0

            return {
                "files": files,
                "symbols": symbols,
                "classes": classes,
                "functions": functions,
                "imports": imports,
                "calls": calls,
                "resolved_calls": resolved_calls,
                "unresolved_calls": unresolved_calls,
                "resolution_rate": resolution_rate,
            }

    def delete_all_calls(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM calls")

    def delete_all_inherits(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM inherits")

    def get_symbols_by_file_id(self, file_id: int) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute(
                "SELECT qualified_name FROM symbols WHERE file_id = ?", (file_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def search_files_by_suffix(self, suffix: str) -> list[dict]:
        with self._read_connect() as conn:
            rows = conn.execute(
                "SELECT path FROM files WHERE path LIKE ?", (f"%{suffix}",)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            for table in self._CLEARABLE_TABLES:
                conn.execute(f"DELETE FROM {table}")
            try:
                conn.execute("DROP TABLE IF EXISTS vec_symbols")
            except sqlite3.OperationalError:
                pass
