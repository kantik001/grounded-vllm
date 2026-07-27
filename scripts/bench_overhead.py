#!/usr/bin/env python3
"""Measure grounded-vllm + guardrails overhead (no GPU required).

Uses httpx ASGITransport for the proxy (no real ports) + live gRPC to guardrails.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from grounded_vllm.client import GuardrailsClient
from grounded_vllm.proxy import create_app

CONTEXT = (
    "Leave Policy: Employees receive 28 paid vacation days per year. "
    "Carry-over limit is 14 days."
)
GOOD_ANSWER = "Employees get 28 paid vacation days."
BAD_ANSWER = "Employees get 99 paid vacation days."

MOCK_COMPLETION = {
    "id": "chatcmpl-mock",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": GOOD_ANSWER},
            "finish_reason": "stop",
        }
    ],
}


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    k = (len(ys) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ys) - 1)
    if f == c:
        return ys[f]
    return ys[f] + (ys[c] - ys[f]) * (k - f)


def summarize(xs: list[float]) -> dict:
    return {
        "n": len(xs),
        "mean_ms": round(statistics.fmean(xs), 3) if xs else 0.0,
        "p50_ms": round(percentile(xs, 50), 3),
        "p95_ms": round(percentile(xs, 95), 3),
        "p99_ms": round(percentile(xs, 99), 3),
        "min_ms": round(min(xs), 3) if xs else 0.0,
        "max_ms": round(max(xs), 3) if xs else 0.0,
    }


def bench_guardrails(addr: str, iters: int, warmup: int) -> dict:
    print(f"bench guardrails @ {addr} …", flush=True)
    client = GuardrailsClient(addr, timeout_s=5.0)
    samples: list[float] = []
    try:
        for i in range(warmup + iters):
            text = GOOD_ANSWER if i % 2 == 0 else BAD_ANSWER
            t0 = time.perf_counter()
            client.verify_text(text, context=CONTEXT)
            dt = (time.perf_counter() - t0) * 1000.0
            if i >= warmup:
                samples.append(dt)
    finally:
        client.close()
    out = {"name": "guardrails_verify_text", "latency": summarize(samples)}
    print(f"  -> p50={out['latency']['p50_ms']}ms p99={out['latency']['p99_ms']}ms", flush=True)
    return out


def bench_proxy_asgi(
    *,
    guardrails: str,
    verify: bool,
    iters: int,
    warmup: int,
    name: str,
) -> dict:
    print(f"bench {name} …", flush=True)

    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from fastapi.testclient import TestClient

    async def chat(request):
        await request.body()
        return JSONResponse(MOCK_COMPLETION)

    upstream_app = Starlette(routes=[Route("/v1/chat/completions", chat, methods=["POST"])])

    import grounded_vllm.proxy as proxy_mod

    class UpstreamClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("transport", None)
            kwargs["transport"] = httpx.ASGITransport(app=upstream_app)
            kwargs["base_url"] = kwargs.get("base_url") or "http://upstream"
            super().__init__(*args, **kwargs)

    original = proxy_mod.httpx.AsyncClient
    proxy_mod.httpx.AsyncClient = UpstreamClient  # type: ignore[misc,assignment]
    try:
        app = create_app(
            upstream="http://upstream",
            guardrails_addr=guardrails,
            verify_enabled=verify,
            block_on_fail=False,
        )
        payload = {
            "model": "mock",
            "messages": [{"role": "user", "content": "How many vacation days?"}],
            "extra_body": {"grounded_context": CONTEXT},
        }
        samples: list[float] = []
        with TestClient(app) as http:
            for i in range(warmup + iters):
                t0 = time.perf_counter()
                r = http.post("/v1/chat/completions", json=payload)
                dt = (time.perf_counter() - t0) * 1000.0
                r.raise_for_status()
                if i >= warmup:
                    samples.append(dt)
    finally:
        proxy_mod.httpx.AsyncClient = original  # type: ignore[misc,assignment]

    out = {"name": name, "latency": summarize(samples)}
    print(f"  -> p50={out['latency']['p50_ms']}ms p99={out['latency']['p99_ms']}ms", flush=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guardrails", default="127.0.0.1:50052")
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--write", type=Path, default=Path("results/overhead.json"))
    args = parser.parse_args()

    results = {
        "benchmark": "grounded-vllm-overhead",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "config": {
            "iters": args.iters,
            "warmup": args.warmup,
            "guardrails": args.guardrails,
            "note": (
                "In-process ASGI mock upstream (no GPU/vLLM). "
                "Isolates gRPC verify + proxy orchestration overhead."
            ),
        },
        "suites": [],
    }

    results["suites"].append(bench_guardrails(args.guardrails, args.iters, args.warmup))
    results["suites"].append(
        bench_proxy_asgi(
            guardrails=args.guardrails,
            verify=False,
            iters=args.iters,
            warmup=args.warmup,
            name="proxy_no_verify",
        )
    )
    results["suites"].append(
        bench_proxy_asgi(
            guardrails=args.guardrails,
            verify=True,
            iters=args.iters,
            warmup=args.warmup,
            name="proxy_with_verify",
        )
    )

    by_name = {s["name"]: s["latency"] for s in results["suites"]}
    results["derived"] = {
        "verify_add_p50_ms": round(
            by_name["proxy_with_verify"]["p50_ms"] - by_name["proxy_no_verify"]["p50_ms"], 3
        ),
        "verify_add_p99_ms": round(
            by_name["proxy_with_verify"]["p99_ms"] - by_name["proxy_no_verify"]["p99_ms"], 3
        ),
        "guardrails_p99_ms": by_name["guardrails_verify_text"]["p99_ms"],
    }

    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)
    print(f"Wrote {args.write}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
