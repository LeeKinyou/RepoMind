"""Tests for VectorStore — covers H5 (configurable dimension) and C2 (SQL injection)."""

from __future__ import annotations

import pytest  # noqa: E402

# Skip if lancedb not installed
pytest.importorskip("lancedb")

from repomind.storage.vector_store import VectorStore, VectorEntry  # noqa: E402


class TestVectorStoreInit:
    def test_default_dimension(self, tmp_dir):
        store = VectorStore(db_path=str(tmp_dir / "vectors"))
        assert store.embedding_dim == 1536

    def test_custom_dimension(self, tmp_dir):
        store = VectorStore(db_path=str(tmp_dir / "vectors"), embedding_dim=768)
        assert store.embedding_dim == 768

    def test_creates_directory(self, tmp_dir):
        path = tmp_dir / "new" / "vectors"
        VectorStore(db_path=str(path))
        assert path.exists()


class TestVectorEntry:
    def test_create_entry(self):
        entry = VectorEntry(id="1", text="hello", vector=[0.1] * 1536)
        assert entry.metadata == {}

    def test_with_metadata(self):
        entry = VectorEntry(
            id="1", text="hello", vector=[0.1] * 1536, metadata={"source": "test"}
        )
        assert entry.metadata["source"] == "test"


class TestVectorStoreCRUD:
    def test_add_search_delete_flow(self, tmp_dir):
        store = VectorStore(db_path=str(tmp_dir / "vectors"), embedding_dim=4)
        entry1 = VectorEntry(
            id="file1.py:func1", text="def func1(): pass", vector=[0.1, 0.2, 0.3, 0.4]
        )
        entry2 = VectorEntry(
            id="file2.py:func2", text="def func2(): pass", vector=[0.5, 0.6, 0.7, 0.8]
        )

        store.add([entry1, entry2])
        assert store.count() == 2

        # Search
        results = store.search([0.1, 0.2, 0.3, 0.4], limit=1)
        assert len(results) == 1
        assert results[0]["id"] == "file1.py:func1"

        # Delete
        store.delete(["file1.py:func1"])
        assert store.count() == 1

        # Clear
        store.clear()
        assert store.count() == 0

    def test_delete_sql_injection_raises(self, tmp_dir):
        store = VectorStore(db_path=str(tmp_dir / "vectors"), embedding_dim=4)
        with pytest.raises(ValueError, match="Invalid ID format"):
            store.delete(["' OR 1=1 --"])
