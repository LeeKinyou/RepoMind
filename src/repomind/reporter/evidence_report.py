"""Evidence reporter for exporting diagnosis results to Markdown and JSON formats."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repomind.models.diagnostic import DiagnosticState

from repomind.models.schemas import RCAResult


class EvidenceReporter:
    """Orchestrates creating and exporting structured diagnosis evidence reports."""

    @staticmethod
    def generate_agent_report(state: "DiagnosticState") -> str:
        """Format a DiagnosticState into a Markdown diagnosis report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# RepoMind Agent Diagnosis Report",
            f"**Generated At**: {timestamp}",
            f"**Total Iterations**: {state.iteration}",
            f"**Stop Reason**: {state.stop_reason or 'Unknown'}",
            "",
            "## 1. Issue",
            f"```\n{state.issue}\n```",
            "",
            "## 2. Hypotheses",
        ]
        
        if state.hypotheses:
            for idx, hyp in enumerate(sorted(state.hypotheses, key=lambda h: h.confidence, reverse=True), 1):
                lines.extend([
                    f"### {idx}. {hyp.description}",
                    f"- **Confidence**: {hyp.confidence:.2f}",
                    f"- **Supporting Evidence IDs**: {', '.join(hyp.supporting_evidence_ids) or 'None'}",
                    f"- **Conflicting Evidence IDs**: {', '.join(hyp.conflicting_evidence_ids) or 'None'}",
                    ""
                ])
        else:
            lines.append("*No hypotheses formulated.*")
            lines.append("")

        lines.append("## 3. Collected Evidence")
        if state.evidences:
            for idx, ev in enumerate(state.evidences, 1):
                lines.extend([
                    f"### Evidence: {ev.evidence_id}",
                    f"- **Source**: `{ev.source}`",
                    f"- **Symbol**: `{ev.symbol}`",
                    f"- **File**: `{ev.file_path}:{ev.start_line}`",
                    f"- **Reason**: {ev.reason}",
                    ""
                ])
                if ev.snippet:
                    lines.extend([
                        "```python",
                        ev.snippet,
                        "```",
                        ""
                    ])
        else:
            lines.append("*No evidence collected.*")
            lines.append("")

        lines.append("## 4. Agent Tool Trace")
        if state.tool_history:
            for inv in state.tool_history:
                status = "Success" if inv.success else f"Failed: {inv.error}"
                lines.extend([
                    f"- **Iter {inv.iteration}**: `{inv.tool_name}` -> {status}",
                    f"  - Arguments: `{json.dumps(inv.arguments)}`",
                    f"  - New Evidence: {len(inv.new_evidence_ids)}"
                ])
        else:
            lines.append("*No tools invoked.*")
            
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def generate_markdown_report(
        rca_result: RCAResult, query: str | None = None
    ) -> str:
        """Format an RCAResult into a comprehensive Markdown diagnosis report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# RepoMind Evidence Report",
            f"**Generated At**: {timestamp}",
            f"**Confidence Score**: {rca_result.confidence * 100:.1f}%",
            "",
            "## 1. Query / Error",
            f"`{query}`" if query else "*No query/error trace provided.*",
            "",
            "## 2. Retrieved Evidence",
        ]

        if rca_result.evidences:
            for idx, ev in enumerate(rca_result.evidences, 1):
                lines.extend(
                    [
                        f"### Evidence {idx}",
                        f"- **File**: `{ev.file_path}`",
                        f"- **Symbol**: `{ev.symbol or 'N/A'}`",
                        f"- **Lines**: {ev.start_line} - {ev.end_line}"
                        if ev.start_line is not None
                        else "- **Lines**: N/A",
                        f"- **Source**: `{ev.source}`",
                    ]
                )
                if ev.score is not None:
                    lines.append(f"- **Score**: {ev.score:.3f}")
                if ev.why_relevant:
                    lines.append(f"- **Why relevant**: {ev.why_relevant}")
                lines.extend(
                    [
                        "",
                        "```python",
                        ev.snippet,
                        "```",
                        "",
                    ]
                )
        else:
            # Fallback to affected symbols if structured evidences aren't present
            if rca_result.affected_symbols:
                for idx, sym in enumerate(rca_result.affected_symbols, 1):
                    lines.extend(
                        [
                            f"### Evidence {idx} (Symbol)",
                            f"- **File**: `{sym.file_path}`",
                            f"- **Symbol**: `{sym.qualified_name}`",
                            f"- **Lines**: {sym.start_line} - {sym.end_line}",
                            "- **Source**: `indexed_symbols`",
                            "",
                        ]
                    )
            else:
                lines.append("*No retrieved code evidence available.*")
                lines.append("")

        lines.extend(
            [
                "## 3. Call Chain Context",
            ]
        )
        if rca_result.call_chain:
            for idx, frame in enumerate(rca_result.call_chain, 1):
                lines.append(f"{idx}. {frame}")
        else:
            lines.append("*No call chain context available.*")
        lines.append("")

        lines.extend(
            [
                "## 4. Root Cause",
                f"> {rca_result.root_cause}",
                "",
                rca_result.explanation
                if rca_result.explanation
                else "No detailed explanation provided.",
                "",
            ]
        )

        if rca_result.suggested_fix:
            lines.extend(
                [
                    "## 5. Suggested Fix",
                    "```python",
                    rca_result.suggested_fix,
                    "```",
                    "",
                ]
            )

        verification_cmd = rca_result.verification_command or "uv run pytest"
        lines.extend(
            [
                "## 6. Verification Command",
                f"`{verification_cmd}`",
                "",
            ]
        )

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
