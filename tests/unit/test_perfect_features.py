"""Unit tests for EvidenceReporter, MCPServer, RepoMindEvaluator, and new CLI commands."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from repomind.cli.app import app
from repomind.eval.evaluator import RepoMindEvaluator
from repomind.mcp.server import MCPServer
from repomind.models.schemas import (
    RCAResult,
    QueryResult,
    SymbolInfo,
    SymbolType,
)
from repomind.reporter.evidence_report import EvidenceReporter


@pytest.fixture
def sample_rca_result():
    """Create a sample RCAResult for testing."""
    return RCAResult(
        root_cause="Division by zero in math_utils.py",
        explanation="The variable denominator was not checked for zero before division.",
        suggested_fix="if denominator == 0:\n    return 0\nreturn numerator / denominator",
        confidence=0.95,
        call_chain=[
            "math_utils.py:10 - divide",
            "calculator.py:25 - calculate",
        ],
        affected_symbols=[
            SymbolInfo(
                name="divide",
                qualified_name="repomind.utils.math_utils.divide",
                type=SymbolType.FUNCTION,
                file_path="src/repomind/utils/math_utils.py",
                start_line=5,
                end_line=15,
                signature="def divide(numerator: int, denominator: int) -> float",
                docstring="Divide two numbers.",
                confidence=1.0,
            )
        ],
        evidence=["math_utils.py:12: => return numerator / denominator"],
    )


class TestEvidenceReporter:
    def test_generate_markdown_report(self, sample_rca_result):
        report = EvidenceReporter.generate_markdown_report(
            sample_rca_result, query="ZeroDivisionError"
        )
        assert "# RepoMind Issue Diagnosis & Evidence Report" in report
        assert "ZeroDivisionError" in report
        assert "Division by zero in math_utils.py" in report
        assert "math_utils.py:10 - divide" in report
        assert "repomind.utils.math_utils.divide" in report
        assert "numerator / denominator" in report

    def test_generate_json_report(self, sample_rca_result):
        report_str = EvidenceReporter.generate_json_report(
            sample_rca_result, query="ZeroDivisionError"
        )
        report = json.loads(report_str)
        assert report["root_cause"] == "Division by zero in math_utils.py"
        assert report["confidence"] == 0.95
        assert report["original_query"] == "ZeroDivisionError"

    def test_save_report(self, tmp_path):
        out_file = tmp_path / "test_report.md"
        EvidenceReporter.save_report("Test Content", str(out_file))
        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == "Test Content"


class TestMCPServer:
    def test_initialize_handshake(self):
        server = MCPServer()
        req = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
        res = server.handle_message(req)
        assert res["id"] == 1
        assert res["result"]["protocolVersion"] == "2024-11-05"
        assert res["result"]["serverInfo"]["name"] == "repomind-mcp-server"
        assert server.initialized is True

    def test_tools_list_before_initialize(self):
        server = MCPServer()
        req = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
        res = server.handle_message(req)
        assert "error" in res
        assert res["error"]["code"] == -32002

    def test_tools_list_after_initialize(self):
        server = MCPServer()
        server.initialized = True
        req = {"jsonrpc": "2.0", "method": "tools/list", "id": 3}
        res = server.handle_message(req)
        assert "result" in res
        tools = res["result"]["tools"]
        assert len(tools) == 4
        tool_names = [t["name"] for t in tools]
        assert "repomind_index_repo" in tool_names
        assert "repomind_search_code" in tool_names
        assert "repomind_expand_call_chain" in tool_names
        assert "repomind_diagnose_issue" in tool_names

    @patch(
        "sys.stdin", StringIO('{"jsonrpc": "2.0", "method": "initialize", "id": 1}\n')
    )
    @patch("sys.stdout", new_callable=StringIO)
    def test_server_loop(self, mock_stdout):
        server = MCPServer()
        server.start()
        output = mock_stdout.getvalue()
        assert "jsonrpc" in output
        assert "2024-11-05" in output


class TestRepoMindEvaluator:
    def test_evaluator_computes_hit_rates(self, tmp_path):
        # Create a mock benchmark cases file
        benchmark_file = tmp_path / "benchmark.json"
        cases = [
            {
                "case_id": "case_test",
                "type": "Code Query",
                "query": "Where is the divide function?",
                "expected_files": ["src/repomind/utils/math_utils.py"],
                "expected_functions": ["divide"],
            }
        ]
        benchmark_file.write_text(json.dumps(cases), encoding="utf-8")

        # Create dummy database file to pass exists check
        db_dir = tmp_path / ".repomind"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "index.db").touch()

        # Mock query service specifically in the evaluator module
        with patch("repomind.eval.evaluator.QueryService") as MockQueryService:
            mock_service = MockQueryService.return_value
            mock_service.search.return_value = QueryResult(
                answer="Found the divide function.",
                symbols=[
                    SymbolInfo(
                        name="divide",
                        qualified_name="repomind.utils.math_utils.divide",
                        type=SymbolType.FUNCTION,
                        file_path=str(tmp_path / "src/repomind/utils/math_utils.py"),
                        start_line=5,
                        end_line=15,
                        signature="def divide()",
                        docstring="mock",
                        confidence=1.0,
                    )
                ],
                elapsed_seconds=0.1,
            )

            evaluator = RepoMindEvaluator(index_dir=str(db_dir))
            res = evaluator.evaluate(str(benchmark_file), project_path=str(tmp_path))

            assert res["success"] is True
            assert res["top1_rate"] == 1.0
            assert res["top3_rate"] == 1.0
            assert res["func_rate"] == 1.0
            assert res["cases_evaluated"] == 1


class TestNewCLICoomands:
    def test_diagnose_command_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "non_existent_file.log"])
        assert result.exit_code != 0
        assert "Trace file not found" in result.output

    def test_eval_command_missing_benchmark(self):
        runner = CliRunner()
        result = runner.invoke(
            app, ["eval", "--benchmark", "non_existent_benchmark.json"]
        )
        assert result.exit_code != 0
        assert "Benchmark file not found" in result.output

    def test_diagnose_command_success(self, tmp_path, sample_rca_result):
        trace_file = tmp_path / "error.log"
        trace_file.write_text("ZeroDivisionError: division by zero", encoding="utf-8")

        with patch(
            "repomind.services.rca_service.RCAService.analyze_trace",
            return_value=sample_rca_result,
        ):
            runner = CliRunner()
            output_report = tmp_path / "diagnose_report.md"
            result = runner.invoke(
                app, ["diagnose", str(trace_file), "--output", str(output_report)]
            )
            assert result.exit_code == 0
            assert "Diagnosis report successfully generated" in result.output
            assert output_report.exists()
            content = output_report.read_text(encoding="utf-8")
            assert "Division by zero in math_utils.py" in content

    def test_eval_command_success(self, tmp_path):
        benchmark_file = tmp_path / "benchmark.json"
        cases = [
            {
                "case_id": "case_test",
                "type": "Code Query",
                "query": "Where is the divide function?",
                "expected_files": ["src/repomind/utils/math_utils.py"],
                "expected_functions": ["divide"],
            }
        ]
        benchmark_file.write_text(json.dumps(cases), encoding="utf-8")

        db_dir = tmp_path / ".repomind"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "index.db").touch()

        mock_result = {
            "success": True,
            "top1_rate": 1.0,
            "top3_rate": 1.0,
            "func_rate": 1.0,
            "cases_evaluated": 1,
        }
        with patch(
            "repomind.eval.evaluator.RepoMindEvaluator.evaluate",
            return_value=mock_result,
        ):
            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "eval",
                    "--project",
                    str(tmp_path),
                    "--benchmark",
                    str(benchmark_file),
                ],
            )
            assert result.exit_code == 0
