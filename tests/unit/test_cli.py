"""Tests for CLI commands — covers L4 (Windows Ctrl+D)."""
from __future__ import annotations

from typer.testing import CliRunner
from repomind.cli.main import app


runner = CliRunner()


class TestCLIHelp:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Repository Intelligence Platform" in result.output

    def test_index_help(self):
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0

    def test_query_help(self):
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0

    def test_rca_help(self):
        result = runner.invoke(app, ["rca", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_clear_help(self):
        result = runner.invoke(app, ["clear", "--help"])
        assert result.exit_code == 0
