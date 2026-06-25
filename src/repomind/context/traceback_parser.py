"""Parser for extracting traceback info from noisy user queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from repomind.context.python_traceback import PythonTracebackParser
from repomind.context.pytest_failure import PytestFailureParser


@dataclass
class StackFrame:
    file_path: str | None
    line_number: int | None
    function_name: str | None
    raw: str


@dataclass
class StackTraceInfo:
    frames: list[StackFrame]
    error_type: str | None
    error_message: str | None


def is_stack_trace(text: str) -> bool:
    """Detect if the text looks like a traceback or error log containing location details."""
    if not text:
        return False
    text_lower = text.lower()
    # Direct traceback markers
    if "traceback" in text_lower:
        return True
    # Exception/Error line markers
    if "exception:" in text_lower or "error:" in text_lower:
        return True
    # Look for files (e.g. ast_parser.py, query_service.py)
    if re.search(r'\b\w+\.py\b', text_lower):
        return True
    # JS/Java stack frame markers
    if re.search(r'\bat\s+[\w.$]+\([\w./\-]+:\d+\)', text):
        return True
    if re.search(r'line\s+\d+', text_lower):
        return True
    return False


def parse_stack_trace(text: str) -> StackTraceInfo:
    """Parse traceback or single-line error log to extract structured StackTraceInfo."""
    frames = []

    # 1. Parse standard python traceback frames: File "...", line \d+, in ...
    py_frame_pattern = re.compile(r'File "([^"]+)", line (\d+), in ([^\s\n\(\)]+)')
    for match in py_frame_pattern.finditer(text):
        frames.append(StackFrame(
            file_path=match.group(1),
            line_number=int(match.group(2)),
            function_name=match.group(3).strip(),
            raw=match.group(0)
        ))

    # 2. Parse java/javascript style stack frames: at module.function(file.py:123)
    js_frame_pattern = re.compile(r'at\s+([a-zA-Z0-9_\-\.]+)\(([^:]+):(\d+)\)')
    for match in js_frame_pattern.finditer(text):
        frames.append(StackFrame(
            file_path=match.group(2),
            line_number=int(match.group(3)),
            function_name=match.group(1).split(".")[-1],
            raw=match.group(0)
        ))

    # 3. Fallback to parsing single-line / informal error reports
    if not frames:
        # Match python filename: e.g. "in ast_parser.py" or "in ast_parser.py at line 45"
        file_match = re.search(r'\bin\s+([a-zA-Z0-9_\-\./]+\.py)\b', text, re.IGNORECASE)
        # Or just any .py file named in the text
        if not file_match:
            file_match = re.search(r'\b([a-zA-Z0-9_\-\./]+\.py)\b', text, re.IGNORECASE)
            
        file_path = file_match.group(1) if file_match else None

        line_match = re.search(r'\bline\s+(\d+)\b', text, re.IGNORECASE)
        line_number = int(line_match.group(1)) if line_match else None

        # Search for function name inside/in/at
        func_matches = re.finditer(r'\b(?:in|inside|at)\s+([a-zA-Z0-9_]+)\b', text, re.IGNORECASE)
        func_name = None
        for m in func_matches:
            candidate = m.group(1)
            # Skip if this candidate is part of a filename
            if f"{candidate.lower()}.py" in text.lower():
                continue
            if candidate.lower() not in ("line", "graph", "relation", "handling", "error", "exception", "validation", "failure") and not candidate.endswith(".py"):
                func_name = candidate

        # Additional heuristics for function name
        if not func_name:
            func_matches2 = re.finditer(r'\bat\s+([a-zA-Z0-9_]+)\b', text, re.IGNORECASE)
            for m in func_matches2:
                candidate = m.group(1)
                if f"{candidate.lower()}.py" in text.lower():
                    continue
                if candidate.lower() not in ("line",) and not candidate.endswith(".py"):
                    func_name = candidate

        if file_path or line_number or func_name:
            frames.append(StackFrame(
                file_path=file_path,
                line_number=line_number,
                function_name=func_name,
                raw=text
            ))

    # Parse error type and message
    error_type = None
    error_message = None

    # Check for "ExceptionName: message" pattern
    exc_match = re.search(r'^([a-zA-Z0-9_\.]+Error|[a-zA-Z0-9_\.]+Exception):\s*(.*)$', text, re.MULTILINE)
    if exc_match:
        error_type = exc_match.group(1).strip()
        error_message = exc_match.group(2).strip()
    else:
        # Extract before first occurrence of "in <file>.py"
        parts = re.split(r'\s+in\s+', text, maxsplit=1)
        if parts and ":" in parts[0]:
            subparts = parts[0].split(":", 1)
            if len(subparts[0].strip().split()) <= 2:
                error_type = subparts[0].strip()
                error_message = subparts[1].strip()

    if error_message:
        msg_parts = re.split(r'\s+in\s+[a-zA-Z0-9_\-\./]+\.py', error_message, flags=re.IGNORECASE)
        if msg_parts:
            error_message = msg_parts[0].strip()

    return StackTraceInfo(
        frames=frames,
        error_type=error_type,
        error_message=error_message
    )


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
