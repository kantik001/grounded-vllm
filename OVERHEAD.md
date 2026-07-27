# Overhead — grounded-vllm + guardrails

Isolates **verify + proxy** cost with an in-process mock upstream (no GPU / no model load).
Generation latency of vLLM is **not** included — add your own TTFT/E2E on top.

## Machine

```text
OS:       Windows 10 (10.0.19045)
CPU:      AMD64 Family 23 Model 8 (Zen+)
Python:   3.12.0
Date:     2026-07-28
Method:   scripts/bench_overhead.py — 20 warmup + 200 iters
Guardrails: grounded-guardrails gRPC :50052 (local)
```

## Results

| Layer | p50 | p95 | p99 | Notes |
|-------|----:|----:|----:|-------|
| `VerifyText` gRPC only | **0.38 ms** | 0.86 ms | **3.34 ms** | Good + bad numeric answers alternating |
| Proxy, verify off | 2.41 ms | 2.95 ms | 3.19 ms | ASGI mock upstream |
| Proxy, verify on | 3.12 ms | 3.66 ms | 3.88 ms | Proxy + `VerifyText` |
| **Verify add (on − off)** | **+0.71 ms** | — | **+0.69 ms** | Marginal cost of grounding check |

Raw JSON: [`results/overhead.json`](results/overhead.json)

## Reproduce

```bash
# terminal A
cd ../grounded-guardrails/go && go run ./cmd/server

# terminal B
cd grounded-vllm
python scripts/bench_overhead.py --write results/overhead.json
```

## Interpretation

- Guardrails unary verify is **sub-millisecond p50** on this CPU; p99 spikes to a few ms (GC / scheduler noise on Windows).
- Putting verify in the OpenAI proxy adds **≈0.7 ms p50/p99** beyond the proxy hop itself.
- Relative to typical local LLM generation (hundreds of ms → seconds), verify overhead is **negligible**.
- Re-measure on your GPU host with real vLLM if you need end-to-end serving numbers.
