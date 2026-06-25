import pytest
from repomind.eval.evaluator import normalize_path, normalize_symbol, is_function_hit
from repomind.context.traceback_parser import is_stack_trace, parse_stack_trace
from repomind.indexer.ast_symbol_indexer import ASTSymbolIndexer


def test_path_normalization():
    p1 = "src/foo/bar.py"
    p2 = ".\\src\\foo\\bar.py"
    p3 = "F:\\workspace\\repo\\src\\foo\\bar.py"

    assert normalize_path(p1) == "src/foo/bar.py"
    assert normalize_path(p2) == "src/foo/bar.py"
    assert normalize_path(p3).endswith("src/foo/bar.py")


def test_stack_trace_parser():
    tb_text = (
        "Traceback (most recent call last):\n"
        '  File "src/retrieval/indexer.py", line 42, in build_index\n'
        "    self.parse_file(path)\n"
        "ValueError: invalid syntax"
    )

    assert is_stack_trace(tb_text) is True

    parsed = parse_stack_trace(tb_text)
    assert len(parsed.frames) == 1
    assert parsed.frames[0].file_path == "src/retrieval/indexer.py"
    assert parsed.frames[0].line_number == 42
    assert parsed.frames[0].function_name == "build_index"
    assert parsed.error_type == "ValueError"
    assert parsed.error_message == "invalid syntax"


def test_informal_stack_trace_parser():
    tb_text = "FileNotFoundError: [Errno 2] No such file or directory in ast_parser.py at line 45 in parse_file"
    assert is_stack_trace(tb_text) is True

    parsed = parse_stack_trace(tb_text)
    assert len(parsed.frames) == 1
    assert parsed.frames[0].file_path == "ast_parser.py"
    assert parsed.frames[0].line_number == 45
    assert parsed.frames[0].function_name == "parse_file"
    assert parsed.error_type == "FileNotFoundError"
    assert parsed.error_message == "[Errno 2] No such file or directory"


def test_function_hit_evaluator():
    # Setup mock actual results and DB symbols
    expected_files = ["src/retrieval/indexer.py"]
    db_symbols = [
        {"name": "build_index", "qualified_name": "repomind.retriever.indexer.build_index", "start_line": 30, "end_line": 50}
    ]

    # Matching case
    actual_ok = {"file_path": "src/retrieval/indexer.py", "name": "build_index", "line_number": 42}
    assert is_function_hit("build_index", expected_files, actual_ok, db_symbols) is True

    # Matching case via name normalization
    actual_ok_norm = {"file_path": "src/retrieval/indexer.py", "name": "Indexer.build_index", "line_number": 42}
    assert is_function_hit("build_index", expected_files, actual_ok_norm, db_symbols) is True

    # Non-matching file (same function name in different file)
    actual_wrong_file = {"file_path": "src/other.py", "name": "build_index", "line_number": 42}
    assert is_function_hit("build_index", expected_files, actual_wrong_file, db_symbols) is False

    # Out of line range match check
    actual_wrong_line = {"file_path": "src/retrieval/indexer.py", "name": "different_function", "line_number": 99}
    assert is_function_hit("build_index", expected_files, actual_wrong_line, db_symbols) is False


def test_ast_symbol_extractor():
    code = (
        "class MyClass:\n"
        "    def method_one(self, x):\n"
        "        pass\n"
        "    async def async_method(self):\n"
        "        pass\n"
        "\n"
        "def top_level_func():\n"
        "    pass\n"
    )

    indexer = ASTSymbolIndexer()
    symbols = indexer.extract_symbols(code, "my_file.py")

    assert len(symbols) == 4
    
    # Check Class
    cls_sym = [s for s in symbols if s.type.value == "class"][0]
    assert cls_sym.name == "MyClass"
    assert cls_sym.qualified_name == "my_file.MyClass"

    # Check Method
    method_sym = [s for s in symbols if s.name == "method_one"][0]
    assert method_sym.type.value == "method"
    assert method_sym.parent_class == "MyClass"

    # Check Async Method
    async_sym = [s for s in symbols if s.name == "async_method"][0]
    assert async_sym.type.value == "method"
    assert async_sym.parent_class == "MyClass"

    # Check Top level Function
    func_sym = [s for s in symbols if s.name == "top_level_func"][0]
    assert func_sym.type.value == "function"
    assert func_sym.parent_class is None
