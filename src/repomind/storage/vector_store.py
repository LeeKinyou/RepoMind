"""LanceDB vector storage for RepoMind."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lancedb
from pydantic import BaseModel, Field


class VectorEntry(BaseModel):
    """A single vector entry for storage."""

    id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStore:
    """LanceDB-based vector storage for code embeddings."""

    def __init__(self, db_path: str = ".repomind/vectors", embedding_dim: int = 1536):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.db = lancedb.connect(str(self.db_path))
        self._table = None

    def _get_table(self):
        """Get or create the embeddings table."""
        if self._table is None:
            try:
                self._table = self.db.open_table("embeddings")
            except (ValueError, KeyError, OSError):
                # Table doesn't exist — create it
                self._table = self.db.create_table(
                    "embeddings", schema=self._make_schema()
                )
        return self._table

    def _make_schema(self):
        import pyarrow as pa

        return pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.embedding_dim)),
                pa.field("metadata", pa.string()),
            ]
        )

    def add(self, entries: list[VectorEntry]) -> None:
        import json

        table = self._get_table()
        data = [
            {
                "id": e.id,
                "text": e.text,
                "vector": e.vector,
                "metadata": json.dumps(e.metadata),
            }
            for e in entries
        ]
        table.add(data)

    def search(self, query_vector: list[float], limit: int = 10) -> list[dict]:
        import json

        table = self._get_table()
        results = table.search(query_vector).limit(limit).to_list()
        for r in results:
            if "metadata" in r and isinstance(r["metadata"], str):
                r["metadata"] = json.loads(r["metadata"])
        return results

    def delete(self, ids: list[str]) -> None:
        import re

        table = self._get_table()
        # Validate each ID to prevent SQL injection (must contain only alphanumeric, underscores, dots, slashes, dashes, colons, at-signs)
        safe_pattern = re.compile(r"^[a-zA-Z0-9_./\-:@]+$")
        for val in ids:
            if not safe_pattern.match(val):
                raise ValueError(f"Invalid ID format: {val!r}")

        if not ids:
            return

        id_list = ", ".join(f"'{s}'" for s in ids)
        table.delete(f"id IN ({id_list})")

    def count(self) -> int:
        return self._get_table().count_rows()

    def clear(self) -> None:
        import logging

        logger = logging.getLogger(__name__)
        try:
            self.db.drop_table("embeddings")
        except Exception as e:
            logger.debug(
                "Table 'embeddings' did not exist or could not be dropped: %s", e
            )
        self._table = None
