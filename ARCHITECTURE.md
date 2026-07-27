# Architecture

## Data path

```text
┌────────────┐   OpenAI JSON    ┌─────────────────┐   OpenAI JSON   ┌──────────┐
│  Client /  │ ───────────────► │  grounded-vllm  │ ──────────────► │   vLLM   │
│ grounded-  │                  │  proxy :8001    │                 │  :8000   │
│ llm server │ ◄─────────────── │                 │ ◄────────────── │          │
└────────────┘   + grounded_    └────────┬────────┘                 └──────────┘
                 verify                  │
                                         │ gRPC VerifyText /
                                         │ VerifyStream
                                         ▼
                               ┌─────────────────────┐
                               │ grounded-guardrails │
                               │       :50052        │
                               └─────────────────────┘
```

## Responsibilities

| Component | Does | Does not |
|-----------|------|----------|
| Proxy | Forward OpenAI traffic; attach/enforce verify | Own weights / KV cache |
| Guardrails client | Call `:50052` | Reimplement numeric/PII rules |
| Logits entry point | Validate `extra_args` | Call gRPC inside `apply()` |

## Context contract

Retrieval context reaches verify via (first match wins):

1. `extra_body.grounded_context`
2. top-level `grounded_context` / `context`
3. chat message with `role: "grounding"`

## Failure policy

| Mode | Behavior |
|------|----------|
| Default | Failed verify → HTTP 422 (`grounded_verify_failed`) |
| `--no-block` | Response returned with `grounded_verify.passed=false` |
| Guardrails down | Soft-skip unless `GROUNDED_VLLM_REQUIRE_GUARDRAILS=1` → 503 |

## Ports (ecosystem)

| Service | Port |
|---------|------|
| Python Retriever (grounded-llm) | `:50051` |
| Guardrails | `:50052` |
| vLLM OpenAI | `:8000` (typical) |
| grounded-vllm proxy | `:8001` (typical) |
