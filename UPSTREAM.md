# Upstream contribution plan (vLLM)

Goal from career plan A2: **merged** useful upstream work + a working adapter (this repo).

## What we need from vLLM

Decoded-text verify at end-of-generation (and optionally mid-stream) without fragile ASGI body rewriting.

Relevant upstream discussion:

- [RFC: External post-generation classifier hook API](https://github.com/vllm-project/vllm/issues/43999)

Until that lands, **grounded-vllm** uses an OpenAI-compatible proxy — production-honest and portable across vLLM versions.

## Contribution sequence (do in order)

1. **Engage the RFC** with a concrete consumer: link this adapter + guardrails `VerifyText` latency numbers.
2. **Docs PR** (low risk): document recommended pattern for external verify proxies / `extra_body` conventions — only if maintainers want it in-tree.
3. **Small bugfix** found while integrating (streaming edge cases, middleware notes).
4. **Hook implementation PR** only after RFC direction is clear — do not fork a parallel plugin API.

## Local logits entry point

Package entry point:

```text
vllm.logits_processors → grounded_vllm.logits_processor:GroundedAdapterLogitsProcessor
```

This validates `SamplingParams.extra_args["grounded_context"]` and does **not** mutate logits. It exists so the adapter is discoverable inside vLLM’s extension surface while verify stays on decoded text.

## Non-goals

- CUDA kernels for PII/numeric (CPU path already µs in guardrails; wait for a measured serving bottleneck)
- Vendoring vLLM
