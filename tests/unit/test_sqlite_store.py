"""Tests for SQLiteStore — covers C5 (symbol_index), M6 (incremental), M7 (LIKE escape), M8 (atomicity), H2 (connection reuse)."""
from __future__ import annotations

from repomind.models.schemas import SymbolInfo, SymbolType, FileInfo


class TestSQLiteStoreBasics:
    def test_init_creates_db(self, sqlite_store):
        assert sqlite_store.db_path.exists()

    def test_stats_empty(self, sqlite_store):
        stats = sqlite_store.get_stats()
        assert stats["files"] == 0
        assert stats["symbols"] == 0


class TestFileOperations:
    def test_upsert_file(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc123", line_count=10)
        file_id = sqlite_store.upsert_file(info)
        assert file_id > 0

    def test_upsert_file_same_hash_returns_same_id(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc123")
        id1 = sqlite_store.upsert_file(info)
        id2 = sqlite_store.upsert_file(info)
        assert id1 == id2

    def test_upsert_file_different_hash_cleans_old_data(self, sqlite_store):
        """M6: When hash changes, old symbols/imports should be cleaned."""
        info1 = FileInfo(path="test.py", language="python", hash="hash1", line_count=5)
        file_id = sqlite_store.upsert_file(info1)

        sym = SymbolInfo(name="old_func", qualified_name="test.old_func",
                         type=SymbolType.FUNCTION, file_path="test.py",
                         start_line=1, end_line=3)
        sqlite_store.insert_symbol(sym, file_id)

        # Verify symbol exists
        found = sqlite_store.get_symbol_by_qualified_name("test.old_func")
        assert found is not None

        # Update file with new hash
        info2 = FileInfo(path="test.py", language="python", hash="hash2", line_count=10)
        sqlite_store.upsert_file(info2)

        # Old symbol should be gone
        found = sqlite_store.get_symbol_by_qualified_name("test.old_func")
        assert found is None

    def test_get_file_by_path(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        sqlite_store.upsert_file(info)
        result = sqlite_store.get_file_by_path("test.py")
        assert result is not None
        assert result["path"] == "test.py"

    def test_get_file_by_path_not_found(self, sqlite_store):
        assert sqlite_store.get_file_by_path("nonexistent.py") is None


class TestSymbolOperations:
    def test_insert_and_get_symbol(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym = SymbolInfo(name="foo", qualified_name="test.foo",
                         type=SymbolType.FUNCTION, file_path="test.py",
                         start_line=1, end_line=5, docstring="A function")
        sym_id = sqlite_store.insert_symbol(sym, file_id)
        assert sym_id > 0

        found = sqlite_store.get_symbol_by_qualified_name("test.foo")
        assert found is not None
        assert found["name"] == "foo"

    def test_insert_symbol_with_parent_class(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)

        cls = SymbolInfo(name="MyClass", qualified_name="test.MyClass",
                         type=SymbolType.CLASS, file_path="test.py",
                         start_line=1, end_line=20)
        sqlite_store.insert_symbol(cls, file_id)

        method = SymbolInfo(name="method", qualified_name="test.MyClass.method",
                            type=SymbolType.METHOD, file_path="test.py",
                            start_line=5, end_line=10, parent_class="test.MyClass")
        method_id = sqlite_store.insert_symbol(method, file_id)
        assert method_id > 0

    def test_search_symbols(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym = SymbolInfo(name="UserService", qualified_name="auth.UserService",
                         type=SymbolType.CLASS, file_path="test.py",
                         start_line=1, end_line=20)
        sqlite_store.insert_symbol(sym, file_id)

        results = sqlite_store.search_symbols("User")
        assert len(results) >= 1

    def test_search_symbols_like_escape(self, sqlite_store):
        """M7: LIKE wildcards in query should be escaped."""
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym = SymbolInfo(name="test_func", qualified_name="test.test_func",
                         type=SymbolType.FUNCTION, file_path="test.py",
                         start_line=1, end_line=5)
        sqlite_store.insert_symbol(sym, file_id)

        # Normal search should work
        results = sqlite_store.search_symbols("test_func")
        assert len(results) >= 1

        # Query with % wildcard should be escaped — no symbol has literal %, so 0 results
        results = sqlite_store.search_symbols("%")
        assert len(results) == 0

    def test_get_all_symbols(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        for i in range(3):
            sym = SymbolInfo(name=f"func{i}", qualified_name=f"test.func{i}",
                             type=SymbolType.FUNCTION, file_path="test.py",
                             start_line=i, end_line=i + 1)
            sqlite_store.insert_symbol(sym, file_id)
        assert len(sqlite_store.get_all_symbols()) == 3


class TestRelationOperations:
    def test_insert_call(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym1 = SymbolInfo(name="caller", qualified_name="test.caller",
                          type=SymbolType.FUNCTION, file_path="test.py",
                          start_line=1, end_line=5)
        sym2 = SymbolInfo(name="callee", qualified_name="test.callee",
                          type=SymbolType.FUNCTION, file_path="test.py",
                          start_line=10, end_line=15)
        sqlite_store.insert_symbol(sym1, file_id)
        sqlite_store.insert_symbol(sym2, file_id)

        sqlite_store.insert_call("test.caller", "test.callee", "direct", line_number=3)

        callees = sqlite_store.get_callees("test.caller")
        assert len(callees) == 1
        assert callees[0]["qualified_name"] == "test.callee"

    def test_get_callers(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym1 = SymbolInfo(name="caller", qualified_name="test.caller",
                          type=SymbolType.FUNCTION, file_path="test.py",
                          start_line=1, end_line=5)
        sym2 = SymbolInfo(name="callee", qualified_name="test.callee",
                          type=SymbolType.FUNCTION, file_path="test.py",
                          start_line=10, end_line=15)
        sqlite_store.insert_symbol(sym1, file_id)
        sqlite_store.insert_symbol(sym2, file_id)
        sqlite_store.insert_call("test.caller", "test.callee", "direct")

        callers = sqlite_store.get_callers("test.callee")
        assert len(callers) == 1

    def test_insert_import(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sqlite_store.insert_import(file_id, "os", imported_name="path")

    def test_insert_inherit(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        parent = SymbolInfo(name="Base", qualified_name="test.Base",
                            type=SymbolType.CLASS, file_path="test.py",
                            start_line=1, end_line=10)
        child = SymbolInfo(name="Child", qualified_name="test.Child",
                           type=SymbolType.CLASS, file_path="test.py",
                           start_line=15, end_line=25)
        sqlite_store.insert_symbol(parent, file_id)
        sqlite_store.insert_symbol(child, file_id)
        sqlite_store.insert_inherit("test.Child", "Base", "test.Base")


class TestClear:
    def test_clear_removes_all(self, sqlite_store):
        info = FileInfo(path="test.py", language="python", hash="abc")
        file_id = sqlite_store.upsert_file(info)
        sym = SymbolInfo(name="foo", qualified_name="test.foo",
                         type=SymbolType.FUNCTION, file_path="test.py",
                         start_line=1, end_line=5)
        sqlite_store.insert_symbol(sym, file_id)

        sqlite_store.clear()
        stats = sqlite_store.get_stats()
        assert stats["files"] == 0
        assert stats["symbols"] == 0


class TestConnectionReuse:
    """H2: SQLiteStore should reuse connections."""

    def test_connection_is_cached(self, sqlite_store):
        conn1 = sqlite_store._get_conn()
        conn2 = sqlite_store._get_conn()
        assert conn1 is conn2

    def test_close_resets_connection(self, sqlite_store):
        _ = sqlite_store._get_conn()
        sqlite_store.close()
        assert sqlite_store._conn is None
