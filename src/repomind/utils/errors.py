"""Custom exceptions for RepoMind."""


class RepoMindError(Exception):
    """Base exception class for RepoMind."""


class IndexingError(RepoMindError):
    """Exception raised during indexing."""


class QueryError(RepoMindError):
    """Exception raised during querying."""


class RCAError(RepoMindError):
    """Exception raised during root cause analysis."""


class GraphLoadError(RepoMindError):
    """Exception raised when loading graph fails."""
