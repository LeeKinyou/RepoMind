"""Workspace resolution and validation for MCP tool calls."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path


def resolve_workspace(
    repo_path: str | None = None,
    *,
    roots: Sequence[str | Path] | None = None,
    environ: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
) -> Path:
    """Resolve a repository path without allowing escapes from MCP roots."""
    environment = os.environ if environ is None else environ
    resolved_roots = [Path(root).resolve() for root in roots or []]

    if repo_path:
        candidate = Path(repo_path).resolve()
        if resolved_roots and not any(
            candidate.is_relative_to(root) for root in resolved_roots
        ):
            raise ValueError(
                f"Repository path '{candidate}' is outside the allowed MCP roots."
            )
    elif resolved_roots:
        candidate = resolved_roots[0]
    elif environment.get("CLAUDE_PROJECT_DIR"):
        candidate = Path(environment["CLAUDE_PROJECT_DIR"]).resolve()
    else:
        candidate = Path(cwd or Path.cwd()).resolve()

    if not candidate.is_dir():
        raise ValueError(f"Repository workspace does not exist: {candidate}")
    return candidate

