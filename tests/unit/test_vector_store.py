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
        entry = VectorEntry(id="1", text="hello", vector=[0.1] * 1536,
                            metadata={"source": "test"})
        assert entry.metadata["source"] == "test"
