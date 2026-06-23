"""Tests for safe MCP workspace resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from repomind.mcp.workspace import resolve_workspace


def test_explicit_repository_path_has_highest_priority(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    explicit = root / "explicit"
    explicit.mkdir()

    resolved = resolve_workspace(
        repo_path=str(explicit),
        roots=[root],
        environ={"CLAUDE_PROJECT_DIR": str(root)},
        cwd=root,
    )

    assert resolved == explicit.resolve()


def test_first_mcp_root_is_used_when_path_is_omitted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    resolved = resolve_workspace(roots=[root], environ={}, cwd=tmp_path)

    assert resolved == root.resolve()


def test_claude_project_dir_is_used_before_cwd(tmp_path):
    claude_root = tmp_path / "claude"
    cwd = tmp_path / "cwd"
    claude_root.mkdir()
    cwd.mkdir()

    resolved = resolve_workspace(
        environ={"CLAUDE_PROJECT_DIR": str(claude_root)},
        cwd=cwd,
    )

    assert resolved == claude_root.resolve()


def test_explicit_path_must_be_inside_allowed_roots(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(ValueError, match="outside the allowed MCP roots"):
        resolve_workspace(repo_path=str(outside), roots=[allowed])


def test_nonexistent_workspace_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        resolve_workspace(repo_path=str(tmp_path / "missing"))


def test_workspace_index_directory_stays_under_repository(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()

    resolved = resolve_workspace(repo_path=str(repository))

    assert Path(resolved / ".repomind").is_relative_to(resolved)
