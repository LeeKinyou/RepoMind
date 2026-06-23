"""Parser for pytest assertion failure output."""

from __future__ import annotations

import re

from repomind.trace.base import ExceptionInfo, ParsedFailure, TraceFrame

_LOCATION_PATTERN = re.compile(
    r"^(.+?\.py):(\d+):\s*([A-Za-z_][\w.]*)\s*$", re.MULTILINE
)
_ERROR_DETAIL_PATTERN = re.compile(r"^\s*E\s+(.*)$", re.MULTILINE)


class PytestFailureParser:
    def can_parse(self, text: str) -> bool:
        return bool(_LOCATION_PATTERN.search(text)) and (
            "AssertionError" in text or bool(_ERROR_DETAIL_PATTERN.search(text))
        )

    def parse(self, text: str) -> ParsedFailure:
        locations = list(_LOCATION_PATTERN.finditer(text))
        frames = [
            TraceFrame(
                file_path=match.group(1),
                line_number=int(match.group(2)),
                function_name="<pytest>",
            )
            for match in locations
        ]

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

