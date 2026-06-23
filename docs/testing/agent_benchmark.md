# RepoMind Agent Benchmark

This document tracks the evaluation of RepoMind's Agentic Diagnostic capabilities against traditional baseline retrieval.

## Methodology

We run a suite of 30-50 real-world issue scenarios. For each scenario, we have a target file and a target function that represents the root cause.

We evaluate two modes:
1. **Evidence Mode**: Pure retrieval (Hybrid Search + 1-hop static expansion). No generative LLM.
2. **Agent Mode**: `DiagnosticAgent` utilizing a ReAct loop to iteratively fetch evidence, guided by hypotheses, up to 5 iterations.

## Metrics

- **Top-1 File Hit Rate**
- **Top-3 File Hit Rate**
- **Function Hit Rate**
- **Average Token Usage**
- **Average Tool Calls**

## Results

*Results pending full dataset completion. To run the benchmark, execute:*

```bash
uv run python eval/run_host_comparison.py
```
