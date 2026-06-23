"""Parser for standard Python tracebacks and exception chains."""

from __future__ import annotations

import re

from repomind.trace.base import ExceptionInfo, ParsedFailure, TraceFrame

_FRAME_PATTERN = re.compile(r'^\s*File "([^"]+)", line (\d+), in (.+)$', re.MULTILINE)
_EXCEPTION_PATTERN = re.compile(
    r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit)):\s*(.*)$",
    re.MULTILINE,
)


class PythonTracebackParser:
    def can_parse(self, text: str) -> bool:
        return "Traceback (most recent call last):" in text and bool(
            _FRAME_PATTERN.search(text)
        )

    def parse(self, text: str) -> ParsedFailure:
        frames = [
            TraceFrame(
                file_path=match.group(1),
                line_number=int(match.group(2)),
                function_name=match.group(3).strip(),
            )
            for match in _FRAME_PATTERN.finditer(text)
        ]
        exceptions = [
            ExceptionInfo(type=match.group(1), message=match.group(2).strip())
            for match in _EXCEPTION_PATTERN.finditer(text)
        ]
        chain_markers = []
        if "The above exception was the direct cause" in text:
            chain_markers.append("direct_cause")
        if "During handling of the above exception" in text:
            chain_markers.append("during_handling")

        warnings = []
        if not frames:
            warnings.append("No Python traceback frames were found.")
        if not exceptions:
            warnings.append("No terminal Python exception was found.")

        return ParsedFailure(
            raw_text=text,
            frames=frames,
            exceptions=exceptions,
            chain_markers=chain_markers,
            warnings=warnings,
        )

