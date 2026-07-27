# grounded-vllm

[![CI](https://github.com/kantik001/grounded-vllm/actions/workflows/ci.yml/badge.svg)](https://github.com/kantik001/grounded-vllm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](pyproject.toml)

**Serving-path adapter:** put grounded verify in front of [vLLM](https://github.com/vllm-project/vllm). Part of the [Grounded](https://github.com/kantik001/grounded-llm) ecosystem.

> vLLM generates → `grounded-vllm` verifies via [grounded-guardrails](https://github.com/kantik001/grounded-guardrails) gRPC `:50052` → client gets a grounded answer (or a block).

```text
Client ──► grounded-vllm :8001 ──► vLLM OpenAI API :8000
                 │
                 └── VerifyText / VerifyStream ──► guardrails :50052
```

## Why this shape

Numeric / PII checks need **decoded text**. A logits processor that calls gRPC every decode step is the wrong abstraction (slow + incomplete). This repo ships:

| Piece | Role |
|-------|------|
| **OpenAI-compatible proxy** | Primary serving-path hook (stream + non-stream) |
| **gRPC client** | `VerifyText` / `VerifyStream` → guardrails |
| **Optional logits entry point** | Validates `extra_args.grounded_context`; no-op on logits (see [UPSTREAM.md](UPSTREAM.md)) |

## Quick start

```bash
pip install -e ".[dev]"

# terminal A — guardrails
cd ../grounded-guardrails/go && go run ./cmd/server   # :50052

# terminal B — vLLM (example)
# vllm serve meta-llama/Meta-Llama-3.1-8B-Instruct --port 8000

# terminal C — adapter
grounded-vllm serve --upstream http://127.0.0.1:8000 --guardrails 127.0.0.1:50052 --port 8001
```

Point [grounded-llm](https://github.com/kantik001/grounded-llm) at the proxy:

```bash
LLM_PROVIDER=vllm
LLM_BASE_URL=http://127.0.0.1:8001/v1
```

### Pass retrieval context

```bash
curl http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "messages": [{"role":"user","content":"What was revenue?"}],
    "extra_body": {"grounded_context": "Q3 revenue figure is 14."}
  }'
```

Successful responses include `grounded_verify: {passed, violations, latency_ms}`. Failures return HTTP **422** with `grounded_verify_failed` (unless `--no-block`).

Unary check without vLLM:

```bash
grounded-vllm verify --text "Revenue was 99." --context "Revenue was 14."
```

## Install with vLLM entry point

```bash
pip install -e ".[vllm]"
# vLLM auto-loads entry point: vllm.logits_processors → grounded_verify
```

## Ecosystem

| Repo | Role |
|------|------|
| [grounded-llm](https://github.com/kantik001/grounded-llm) | Cited RAG + Spec |
| [grounded-guardrails](https://github.com/kantik001/grounded-guardrails) | Verify service `:50052` |
| [grounded-bench](https://github.com/kantik001/grounded-bench) | NVR / CP / HR / RR |
| **grounded-vllm** | Serving-path verify adapter |

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [UPSTREAM.md](UPSTREAM.md) — contribution plan toward vLLM post-generation hooks
- [CHANGELOG.md](CHANGELOG.md)

## Status

Shipped (v0.1):

- Proxy `/v1/chat/completions` + `/v1/completions` (stream / non-stream)
- Guardrails gRPC client + CLI
- Optional logits-processor entry point (validate-only)
- CI unit tests (no GPU required)

Next: tighter streaming session for `VerifyStream`, measured p99 overhead table, upstream docs/RFC engagement.

## License

MIT
