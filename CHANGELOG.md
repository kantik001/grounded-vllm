# Changelog

## [0.1.0] - 2026-07-28

### Added

- OpenAI-compatible proxy (`grounded-vllm serve`) with VerifyText / VerifyStream via grounded-guardrails `:50052`
- CLI `verify` for unary checks
- Optional `vllm.logits_processors` entry point (validate `grounded_context`, no-op logits)
- Architecture + upstream contribution notes
- CI unit tests (no GPU)
