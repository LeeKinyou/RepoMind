"""Tests for path utilities — H1 (Windows paths)."""
from __future__ import annotations

from repomind.utils.path_utils import path_to_module


class TestPathToModule:
    def test_simple_path(self):
        assert path_to_module("auth/login.py") == "auth.login"

    def test_nested_path(self):
        assert path_to_module("src/pkg/module.py") == "src.pkg.module"

    def test_init_file(self):
        assert path_to_module("pkg/__init__.py") == "pkg"

    def test_with_project_root(self):
        result = path_to_module("/home/user/project/auth/login.py", "/home/user/project")
        assert result == "auth.login"

    def test_with_project_root_no_match(self):
        result = path_to_module("/other/path/login.py", "/home/user/project")
        # Absolute path that doesn't match root gets a leading dot from "/other" -> ".other"
        assert result == ".other.path.login"

    def test_windows_backslash(self):
        """H1: Backslashes should be normalized."""
        result = path_to_module("auth\\login.py")
        assert result == "auth.login"

    def test_windows_absolute_path(self):
        result = path_to_module("C:\\Users\\dev\\project\\auth\\login.py")
        assert "auth.login" in result

    def test_no_extension(self):
        result = path_to_module("auth/login")
        assert result == "auth.login"
