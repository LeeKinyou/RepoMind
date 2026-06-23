"""Path utilities for RepoMind."""

from __future__ import annotations

from pathlib import PurePosixPath, Path


def path_to_module(file_path: str, project_root: str = "") -> str:
    """Convert file path to Python module path (POSIX style).

    Args:
        file_path: Absolute or relative file path.
        project_root: Project root to make path relative to.

    Returns:
        Python module path with dots (e.g., "auth.service").
    """
    p = Path(file_path)
    if project_root:
        try:
            p = p.resolve().relative_to(Path(project_root).resolve())
        except ValueError:
            pass
    if p.drive:
        p = Path(str(p)[len(p.drive) :])
    posix = PurePosixPath(p.as_posix())
    module = str(posix).replace("/", ".").replace(".py", "")
    if module.endswith(".__init__"):
        module = module[:-9]
    return module
