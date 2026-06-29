# RepoMind Failure Analysis Report

## Summary

- **Total Cases**: 1
- **Top-1 File Hit Rate**: 100.0%
- **Top-3 File Hit Rate**: 100.0%
- **Function Hit Rate**: 100.0%
- **Avg Latency**: 0.000s
- **Generated At**: 2026-06-29T21:07:27.836599

## Failure Categories

| Category | Count | Description |
|---|---:|---|
| missed_recall | 0 | correct file not in top-k |
| ranking_error | 0 | correct file in top-k but not top-1 |
| function_miss | 0 | correct file found but expected function not found |
| evaluator_warning | 0 | suspicious metric inconsistency |
| stacktrace_parse_miss | 0 | stack trace case failed due to missing path/function extraction |

## High Value Fix Cases

These are cases where the correct file is retrieved in top-3 but not ranked as top-1. They are highly optimized via reranking.

| Case ID | Expected File | Top-1 Returned File | Top-3 Returned Files |
|---|---|---|---|

## Case Details
