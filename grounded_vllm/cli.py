"""CLI: grounded-vllm serve | verify."""

from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from grounded_vllm import DEFAULT_GUARDRAILS_ADDR, DEFAULT_UPSTREAM, __version__
from grounded_vllm.client import GuardrailsClient
from grounded_vllm.proxy import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grounded-vllm")
    parser.add_argument("--version", action="version", version=f"grounded-vllm {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="OpenAI-compatible proxy in front of vLLM")
    p_serve.add_argument("--upstream", default=DEFAULT_UPSTREAM, help="vLLM OpenAI base URL")
    p_serve.add_argument("--guardrails", default=DEFAULT_GUARDRAILS_ADDR, help="host:port")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8001)
    p_serve.add_argument("--no-verify", action="store_true")
    p_serve.add_argument("--no-block", action="store_true", help="Annotate failures but do not block")

    p_verify = sub.add_parser("verify", help="Unary VerifyText against guardrails")
    p_verify.add_argument("--guardrails", default=DEFAULT_GUARDRAILS_ADDR)
    p_verify.add_argument("--text", required=True)
    p_verify.add_argument("--context", default="")

    args = parser.parse_args(argv)

    if args.cmd == "serve":
        app = create_app(
            upstream=args.upstream,
            guardrails_addr=args.guardrails,
            verify_enabled=not args.no_verify,
            block_on_fail=not args.no_block,
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0

    if args.cmd == "verify":
        with GuardrailsClient(args.guardrails) as client:
            verdict = client.verify_text(args.text, context=args.context)
        print(json.dumps({
            "passed": verdict.passed,
            "violations": verdict.violations,
            "latency_ms": verdict.latency_ms,
        }, indent=2))
        return 0 if verdict.passed else 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
