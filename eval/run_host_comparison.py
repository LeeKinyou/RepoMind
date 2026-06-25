"""Run comparison between retrieval modes and Agent orchestration modes."""

import os
import json
import argparse
import time
from pathlib import Path
from repomind.eval.evaluator import RepoMindEvaluator


def main():
    parser = argparse.ArgumentParser(
        description="Run RepoMind Host Comparison Benchmark"
    )
    parser.add_argument("--project", default=".", help="Project root")
    parser.add_argument(
        "--cases",
        default="eval/cases/benchmark_cases_reviewed.json",
        help="Path to benchmark cases",
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=["keyword_only", "symbol_only", "hybrid", "full"],
        help="Retrieval mode to evaluate",
    )
    parser.add_argument(
        "--compare-modes",
        action="store_true",
        help="Compare all retrieval modes in a benchmark run",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Only run RAG retrieval evaluation, skip Agent evaluation",
    )
    parser.add_argument(
        "--sandbox",
        default="auto",
        choices=["auto", "docker", "subprocess"],
        help="Sandbox mode ('auto', 'docker', or 'subprocess')",
    )
    args = parser.parse_args()

    os.environ["REPOMIND_SANDBOX_MODE"] = args.sandbox

    project = Path(args.project).resolve()
    cases_file = Path(args.cases).resolve()

    if not cases_file.exists():
        print(f"Error: Cases file not found at {cases_file}")
        return

    print("=== RepoMind Comparison Benchmark ===")

    evaluator = RepoMindEvaluator(index_dir=str(project / ".repomind"))

    if args.compare_modes:
        print("\nRunning Comparative Modes Evaluation...")
        modes = ["keyword_only", "symbol_only", "hybrid", "full"]
        mode_results = {}

        for mode in modes:
            print(f"\n>>> Evaluating Retrieval Mode: {mode}...")
            start_t = time.time()
            res = evaluator.evaluate(
                str(cases_file), project_path=str(project), use_agent=False, mode=mode
            )
            latency = time.time() - start_t
            if res.get("success"):
                mode_results[mode] = {
                    "top1_rate": res["top1_rate"],
                    "top3_rate": res["top3_rate"],
                    "func_rate": res["func_rate"],
                    "latency": latency / res["cases_evaluated"] if res["cases_evaluated"] else 0.0
                }

        # Print Markdown Comparison Table
        print("\n=== Comparative Evaluation Summary ===")
        print("| Mode | Top-1 File Hit | Top-3 File Hit | Function Hit | Avg Latency |")
        print("|---|---:|---:|---:|---:|")
        for mode, metrics in mode_results.items():
            print(
                f"| {mode} | {metrics['top1_rate']*100:.1f}% | {metrics['top3_rate']*100:.1f}% | {metrics['func_rate']*100:.1f}% | {metrics['latency']:.3f}s |"
            )
        
        # Save compare modes result
        compare_report_path = Path("docs/testing/retrieval_comparison.json")
        compare_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(compare_report_path, "w", encoding="utf-8") as f:
            json.dump(mode_results, f, indent=2)
        print(f"\nComparative report saved to {compare_report_path}")
        return

    # Standard two-stage evaluation: RAG Retrieval (with chosen mode) vs Agent Orchestration
    print(f"\nRunning RAG Retrieval Mode ({args.mode}) Evaluation...")
    res_rag = evaluator.evaluate(
        str(cases_file), project_path=str(project), use_agent=False, mode=args.mode
    )

    if not res_rag.get("success"):
        print("RAG Retrieval Mode Evaluation failed.")
        return

    if args.no_agent:
        print("\nSkipping Agent Orchestration Mode Evaluation (--no-agent is set).")
        report = {
            "Evidence Mode": {
                "top1_rate": res_rag["top1_rate"],
                "top3_rate": res_rag["top3_rate"],
                "func_rate": res_rag["func_rate"],
            }
        }
        report_path = Path("docs/testing/agent_benchmark_reviewed.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nComparison report saved to {report_path}")
        return

    print("\nRunning Agent Orchestration Mode Evaluation...")
    res_agent = evaluator.evaluate(
        str(cases_file), project_path=str(project), use_agent=True, mode=args.mode
    )

    if not res_agent.get("success"):
        print("Agent Orchestration Mode Evaluation failed.")
        return

    report = {
        "Evidence Mode": {
            "top1_rate": res_rag["top1_rate"],
            "top3_rate": res_rag["top3_rate"],
            "func_rate": res_rag["func_rate"],
        },
        "Agent Mode": {
            "top1_rate": res_agent["top1_rate"],
            "top3_rate": res_agent["top3_rate"],
            "func_rate": res_agent["func_rate"],
        },
    }

    report_path = Path("docs/testing/agent_benchmark_reviewed.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nComparison report saved to {report_path}")


if __name__ == "__main__":
    main()
