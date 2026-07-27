# Changelog

## [0.1.0] - 2026-07-28

### Added

- OpenAI-compatible proxy (`grounded-vllm serve`) with VerifyText / VerifyStream via grounded-guardrails `:50052`
- CLI `verify` for unary checks
- Optional `vllm.logits_processors` entry point (validate `grounded_context`, no-op logits)
- Architecture + upstream contribution notes
- CI unit tests (no GPU)
- Overhead bench (`scripts/bench_overhead.py`) + [OVERHEAD.md](OVERHEAD.md) — verify add ≈ **0.7 ms** p50/p99
