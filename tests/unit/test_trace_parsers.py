"""Tests for Python traceback and pytest failure parsers."""

from __future__ import annotations

from repomind.trace.pytest_failure import PytestFailureParser
from repomind.trace.python_traceback import PythonTracebackParser


def test_python_traceback_parser_extracts_frames_and_final_exception():
    text = """Traceback (most recent call last):
  File "/workspace/app.py", line 8, in run
    load_user()
  File "/workspace/users.py", line 12, in load_user
    raise ValueError("missing")
ValueError: missing
"""

    parsed = PythonTracebackParser().parse(text)

    assert [frame.function_name for frame in parsed.frames] == ["run", "load_user"]
    assert parsed.exceptions[-1].type == "ValueError"
    assert parsed.exceptions[-1].message == "missing"
    assert parsed.proximate_frame.line_number == 12


def test_python_traceback_parser_preserves_chained_exceptions():
    text = """Traceback (most recent call last):
  File "/workspace/repository.py", line 4, in load
    raise KeyError("id")
KeyError: 'id'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/workspace/service.py", line 10, in run
    raise RuntimeError("load failed")
RuntimeError: load failed
"""

    parsed = PythonTracebackParser().parse(text)

    assert [error.type for error in parsed.exceptions] == ["KeyError", "RuntimeError"]
    assert parsed.chain_markers == ["direct_cause"]
    assert parsed.proximate_frame.file_path == "/workspace/service.py"


def test_pytest_failure_parser_extracts_location_and_assertion():
    text = """________________________ test_total ________________________

    def test_total():
>       assert total([1, 2]) == 4
E       assert 3 == 4

tests/test_math.py:8: AssertionError
"""

    parser = PytestFailureParser()
    assert parser.can_parse(text)

    parsed = parser.parse(text)

    assert parsed.frames[-1].file_path == "tests/test_math.py"
    assert parsed.frames[-1].line_number == 8
    assert parsed.exceptions[-1].type == "AssertionError"
    assert parsed.exceptions[-1].message == "assert 3 == 4"

