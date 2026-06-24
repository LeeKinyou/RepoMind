"""Parser for pytest assertion failure output."""

from __future__ import annotations

import re

from repomind.context.trace_parser import ExceptionInfo, ParsedFailure, TraceFrame

_LOCATION_PATTERN = re.compile(
    r"^(.+?\.py):(\d+):\s*([^\n]+?)(?:\n[ \t]+(?!E\s+)([^\n]+))?$", 
    re.MULTILINE
)
_ERROR_DETAIL_PATTERN = re.compile(r"^\s*E\s+(.*)$", re.MULTILINE)


class PytestFailureParser:
    def can_parse(self, text: str) -> bool:
        return bool(_LOCATION_PATTERN.search(text)) and (
            "AssertionError" in text or bool(_ERROR_DETAIL_PATTERN.search(text))
        )

    def parse(self, text: str) -> ParsedFailure:
        locations = list(_LOCATION_PATTERN.finditer(text))
        frames = []
        for match in locations:
            code_line = match.group(4).strip() if match.group(4) else None
            if not code_line:
                for line in text.splitlines():
                    if line.strip().startswith(">"):
                        code_line = line.strip().lstrip(">").strip()
                        break
            frames.append(
                TraceFrame(
                    file_path=match.group(1),
                    line_number=int(match.group(2)),
                    function_name="<pytest>",
                    code_line=code_line,
                )
            )

        error_type = locations[-1].group(3) if locations else "AssertionError"
        details = [match.group(1).strip() for match in _ERROR_DETAIL_PATTERN.finditer(text)]
        message = details[-1] if details else ""
        exceptions = [ExceptionInfo(type=error_type, message=message)]

        return ParsedFailure(
            raw_text=text,
            frames=frames,
            exceptions=exceptions,
            warnings=[] if frames else ["No pytest failure location was found."],
        )

