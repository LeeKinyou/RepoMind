"""Shared fixtures for RepoMind tests."""

from __future__ import annotations


import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_python_code():
    """Sample Python source code for parser tests."""
    return '''
import os
from pathlib import Path as P
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


def helper(x: int) -> str:
    """A helper function."""
    return str(x)


def process(data: dict[str, list[int]]) -> dict[str, list[int]]:
    """Process nested data."""
    return data
'''


@pytest.fixture
def sample_trace():
    """Sample Python stack trace for RCA tests."""
    return """Traceback (most recent call last):
  File "/app/services/auth.py", line 42, in login
    user = db.query(User, username)
  File "/app/database/query.py", line 15, in query
    result = self.execute(sql)
  File "/app/database/connection.py", line 88, in execute
    cursor.execute(sql, params)
sqlite3.OperationalError: no such table: users"""


@pytest.fixture
def sqlite_store(tmp_dir):
    """Create a fresh SQLiteStore for testing."""
    from repomind.storage.sqlite_store import SQLiteStore

    db_path = str(tmp_dir / "test.db")
    store = SQLiteStore(db_path)
    yield store
    store.close()


@pytest.fixture
def graph_store():
    """Create a fresh GraphStore for testing."""
    from repomind.storage.graph_store import GraphStore

    return GraphStore()
