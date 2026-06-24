"""Parser for extracting traceback info from noisy user queries."""

from __future__ import annotations

from repomind.context.python_traceback import PythonTracebackParser
from repomind.context.pytest_failure import PytestFailureParser


class TracebackQueryParser:
    """Wrapper parser to check if a query contains a traceback and parse its components."""

    def __init__(self, project_root: str = ""):
        self.python_parser = PythonTracebackParser()
        self.pytest_parser = PytestFailureParser()
        self.project_root = project_root

    def parse_query(self, query: str) -> dict:
        """Parse a query, returning a dict of structured traceback components if found."""
        is_python = self.python_parser.can_parse(query)
        is_pytest = self.pytest_parser.can_parse(query)

        if not is_python and not is_pytest:
            return {
                "is_traceback": False,
                "frames": [],
                "exception_type": None,
                "exception_message": None,
            }

        parser = self.python_parser if is_python else self.pytest_parser
        parsed = parser.parse(query)

        from pathlib import Path
        frames = []
        for frame in parsed.frames:
            fpath = frame.file_path.replace("\\", "/")
            if self.project_root:
                try:
                    p = Path(frame.file_path).resolve()
                    root_path = Path(self.project_root).resolve()
                    if p.is_relative_to(root_path):
                        fpath = p.relative_to(root_path).as_posix()
                except Exception:
                    pass
            frames.append({
                "file_path": fpath,
                "line_number": frame.line_number,
                "function_name": frame.function_name,
                "code_line": frame.code_line,
            })

        exc_type = None
        exc_msg = None
        if parsed.exceptions:
            exc = parsed.exceptions[-1]
            exc_type = exc.type
            exc_msg = exc.message

        return {
            "is_traceback": True,
            "frames": frames,
            "exception_type": exc_type,
            "exception_message": exc_msg,
        }
