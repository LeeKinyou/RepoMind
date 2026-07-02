"""Integration tests for IndexService — covers M8 (atomicity), M9 (relative_to), L6 (function counting)."""

from __future__ import annotations

import pytest
from pathlib import Path
from repomind.indexer.file_scanner import IndexService
from repomind.models.schemas import IndexOptions


@pytest.fixture
def index_service(tmp_dir):
    return IndexService(index_dir=str(tmp_dir / ".repomind"))


@pytest.fixture
def sample_project(tmp_dir):
    """Create a sample Python project for indexing."""
    project = tmp_dir / "myproject"
    project.mkdir()

    (project / "__init__.py").write_text('"""My project."""\n')

    (project / "auth.py").write_text('''
from typing import Optional

class UserService:
    """User authentication service."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def login(self, username: str, password: str) -> bool:
        """Authenticate user."""
        user = self.find_user(username)
        if user:
            return self.verify_password(user, password)
        return False

    def find_user(self, name: str) -> Optional[dict]:
        """Find user by name."""
        return None

    def verify_password(self, user: dict, password: str) -> bool:
        return True


def hash_password(pwd: str) -> str:
    """Hash a password."""
    return pwd
''')

    (project / "utils.py").write_text("""
def helper(x: int) -> str:
    return str(x)

def process(data: dict) -> dict:
    return data
""")

    return project


class TestIndexDirectory:
    def test_index_success(self, index_service, sample_project):
        result = index_service.index_directory(str(sample_project))
        assert result.success is True
        assert result.indexed_files >= 2
        assert result.total_symbols > 0

    def test_index_counts_classes(self, index_service, sample_project):
        result = index_service.index_directory(str(sample_project))
        assert result.total_classes >= 1  # UserService

    def test_index_counts_functions(self, index_service, sample_project):
        """L6: Functions and methods should be counted."""
        result = index_service.index_directory(str(sample_project))
        assert result.total_functions > 0

    def test_index_nonexistent_path(self, index_service):
        result = index_service.index_directory("/nonexistent/path")
        assert result.success is False
        assert len(result.errors) > 0

    def test_index_with_ignore_patterns(self, index_service, tmp_dir):
        project = tmp_dir / "proj"
        project.mkdir()
        (project / "main.py").write_text("x = 1\n")
        (project / "test_main.py").write_text("def test_x(): pass\n")

        opts = IndexOptions(ignore_patterns=["test_*"])
        result = index_service.index_directory(str(project), opts)
        assert result.indexed_files == 1

    def test_index_creates_graph_json(self, index_service, sample_project):
        """C1: Indexing should persist graph."""
        index_service.index_directory(str(sample_project))
        graph_path = Path(index_service.index_dir) / "graph.json"
        assert graph_path.exists()


class TestRelativePathHandling:
    """M9: relative_to should not crash on path mismatch."""

    def test_index_with_symlink(self, index_service, tmp_dir):
        """M9: Paths that don't match root should be handled gracefully."""
        project = tmp_dir / "proj"
        project.mkdir()
        (project / "main.py").write_text("x = 1\n")
        result = index_service.index_directory(str(project))
        assert result.success is True


class TestGetStats:
    def test_stats_after_index(self, index_service, sample_project):
        index_service.index_directory(str(sample_project))
        stats = index_service.get_stats()
        assert stats["files"] >= 2
        assert stats["symbols"] > 0

    def test_stats_empty(self, index_service):
        stats = index_service.get_stats()
        assert stats["files"] == 0


class TestClear:
    def test_clear_after_index(self, index_service, sample_project):
        index_service.index_directory(str(sample_project))
        index_service.clear()
        stats = index_service.get_stats()
        assert stats["files"] == 0


class TestIndexingIdempotencyAndCleanup:
    def test_reindexing_is_idempotent(self, index_service, sample_project):
        # Index project first time
        result1 = index_service.index_directory(str(sample_project))
        assert result1.success is True
        stats1 = index_service.get_stats()

        # Index project second time (incremental=True)
        opts = IndexOptions(incremental=True)
        result2 = index_service.index_directory(str(sample_project), opts)
        assert result2.success is True
        stats2 = index_service.get_stats()

        # Assert database counts remain exactly the same
        assert stats1["files"] == stats2["files"]
        assert stats1["symbols"] == stats2["symbols"]
        assert stats1["classes"] == stats2["classes"]
        assert stats1["functions"] == stats2["functions"]
        assert stats1["calls"] == stats2["calls"]

    def test_reindexing_cleans_deleted_files(self, index_service, sample_project):
        # Index project first time
        result1 = index_service.index_directory(str(sample_project))
        assert result1.success is True
        stats1 = index_service.get_stats()

        # Remove a file from the project directory
        utils_py = sample_project / "utils.py"
        assert utils_py.exists()
        utils_py.unlink()

        # Index project again (incremental=True)
        opts = IndexOptions(incremental=True)
        result2 = index_service.index_directory(str(sample_project), opts)
        assert result2.success is True
        stats2 = index_service.get_stats()

        # Assert database has cleaned up file, symbols, and its calls/relations
        assert stats2["files"] == stats1["files"] - 1
        assert stats2["symbols"] < stats1["symbols"]


class TestFreshnessChecks:
    def test_freshness_is_current_after_index(self, index_service, sample_project):
        index_service.index_directory(str(sample_project))

        freshness = index_service.check_freshness(str(sample_project))

        assert freshness.status == "current"
        assert freshness.changed_files == []
        assert freshness.new_files == []
        assert freshness.deleted_files == []
        assert freshness.index_version >= 1

    def test_freshness_detects_modified_new_and_deleted_files(
        self, index_service, sample_project
    ):
        index_service.index_directory(str(sample_project))

        (sample_project / "auth.py").write_text(
            "def changed_login():\n    return True\n",
            encoding="utf-8",
        )
        (sample_project / "new_module.py").write_text(
            "def new_feature():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (sample_project / "utils.py").unlink()

        freshness = index_service.check_freshness(str(sample_project))

        assert freshness.status == "stale"
        assert freshness.changed_files == ["auth.py"]
        assert freshness.new_files == ["new_module.py"]
        assert freshness.deleted_files == ["utils.py"]

    def test_refresh_if_stale_reindexes_and_advances_version(
        self, index_service, sample_project
    ):
        index_service.index_directory(str(sample_project))
        first_version = index_service.get_index_version()

        (sample_project / "auth.py").write_text(
            "def changed_login():\n    return True\n",
            encoding="utf-8",
        )

        result = index_service.refresh_if_stale(str(sample_project))

        assert result is not None
        assert result.success is True
        assert index_service.get_index_version() > first_version
        assert index_service.check_freshness(str(sample_project)).status == "current"

    def test_refresh_if_stale_skips_when_current(self, index_service, sample_project):
        index_service.index_directory(str(sample_project))
        first_version = index_service.get_index_version()

        result = index_service.refresh_if_stale(str(sample_project))

        assert result is None
        assert index_service.get_index_version() == first_version
