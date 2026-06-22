"""Evidence reporter for exporting diagnosis results to Markdown and JSON formats."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from repomind.models.schemas import RCAResult


class EvidenceReporter:
    """Orchestrates creating and exporting structured diagnosis evidence reports."""

    @staticmethod
    def generate_markdown_report(
        rca_result: RCAResult, query: str | None = None
    ) -> str:
        """Format an RCAResult into a comprehensive Markdown diagnosis report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# RepoMind Issue Diagnosis & Evidence Report",
            f"**Generated At**: {timestamp}",
            f"**Confidence Score**: {rca_result.confidence * 100:.1f}%",
        ]
        if query:
            lines.append(f"**Original Query / Error**: `{query}`")
        lines.append("")

        lines.extend(
            [
                "## 1. Root Cause Summary",
                f"> {rca_result.root_cause}",
                "",
                "## 2. Detailed Explanation",
                rca_result.explanation
                if rca_result.explanation
                else "No detailed explanation provided.",
                "",
            ]
        )

        if rca_result.suggested_fix:
            lines.extend(
                [
                    "## 3. Suggested Code Fix",
                    "```python",
                    rca_result.suggested_fix,
                    "```",
                    "",
                ]
            )

        lines.extend(
            [
                "## 4. Call Chain Trace",
            ]
        )
        if rca_result.call_chain:
            for idx, frame in enumerate(rca_result.call_chain, 1):
                lines.append(f"{idx}. {frame}")
        else:
            lines.append("*No call chain trace available.*")
        lines.append("")

        lines.extend(
            [
                "## 5. Affected Code Symbols & Evidence Files",
            ]
        )
        if rca_result.affected_symbols:
            for sym in rca_result.affected_symbols:
                lines.extend(
                    [
                        f"### Symbol: `{sym.qualified_name}`",
                        f"- **Type**: `{sym.type.value}`",
                        f"- **File Path**: `{sym.file_path}`",
                        f"- **Line Range**: Lines {sym.start_line} - {sym.end_line}",
                    ]
                )
                if sym.signature:
                    lines.append(f"- **Signature**: `{sym.signature}`")
                if sym.docstring:
                    lines.append(f"- **Docstring**: *{sym.docstring.strip()}*")
                lines.append("")
        else:
            lines.append("*No affected symbols indexed.*")
        lines.append("")

        lines.extend(
            [
                "## 6. Diagnostic Evidence Logs",
            ]
        )
        if rca_result.evidence:
            for ev in rca_result.evidence:
                lines.append(f"- {ev}")
        else:
            lines.append("*No specific evidence lines recorded.*")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_json_report(rca_result: RCAResult, query: str | None = None) -> str:
        """Format an RCAResult into a structured JSON string."""
        data = rca_result.model_dump()
        data["generated_at"] = datetime.now().isoformat()
        if query:
            data["original_query"] = query
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def save_report(report_content: str, output_path: str) -> None:
        """Write the generated report to a specified file path."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_content, encoding="utf-8")
