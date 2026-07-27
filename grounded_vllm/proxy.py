"""OpenAI-compatible reverse proxy that verifies generations via guardrails."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import grpc
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from grounded_vllm.client import GuardrailsClient
from grounded_vllm.openai_util import (
    assistant_text_from_chat_completion,
    assistant_text_from_completion,
    extract_grounded_context,
    stream_delta_text,
)

log = logging.getLogger("grounded_vllm.proxy")

PASS_THROUGH_HEADERS = ("authorization", "openai-organization", "x-request-id")


def create_app(
    *,
    upstream: str,
    guardrails_addr: str,
    timeout_s: float = 120.0,
    verify_enabled: bool = True,
    block_on_fail: bool = True,
) -> FastAPI:
    upstream = upstream.rstrip("/")
    guardrails = GuardrailsClient(guardrails_addr)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        guardrails.close()

    app = FastAPI(title="grounded-vllm", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "upstream": upstream, "guardrails": guardrails_addr}

    @app.get("/v1/models")
    async def models(request: Request) -> Response:
        return await _proxy_raw(request, "GET", "/v1/models")

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        body = await request.json()
        if body.get("stream"):
            return await _proxy_stream(request, body, kind="chat")
        return await _proxy_and_verify(request, body, kind="chat")

    @app.post("/v1/completions")
    async def completions(request: Request) -> Response:
        body = await request.json()
        if body.get("stream"):
            return await _proxy_stream(request, body, kind="completion")
        return await _proxy_and_verify(request, body, kind="completion")

    async def _proxy_raw(request: Request, method: str, path: str, json_body: Any = None) -> Response:
        headers = _forward_headers(request)
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            resp = await http.request(method, f"{upstream}{path}", headers=headers, json=json_body)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
        )

    async def _proxy_and_verify(request: Request, body: dict[str, Any], *, kind: str) -> Response:
        headers = _forward_headers(request)
        path = "/v1/chat/completions" if kind == "chat" else "/v1/completions"
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            resp = await http.post(f"{upstream}{path}", headers=headers, json=body)
        if resp.status_code >= 400:
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type"),
            )

        payload = resp.json()
        if not verify_enabled:
            return JSONResponse(payload, status_code=resp.status_code)

        text = (
            assistant_text_from_chat_completion(payload)
            if kind == "chat"
            else assistant_text_from_completion(payload)
        )
        context = extract_grounded_context(body)
        try:
            verdict = guardrails.verify_text(text, context=context)
        except grpc.RpcError as e:
            log.warning("guardrails unavailable: %s", e)
            if block_on_fail and _require_guardrails():
                return JSONResponse(
                    {"error": {"message": f"guardrails unavailable: {e}", "type": "guardrails_error"}},
                    status_code=503,
                )
            payload.setdefault("grounded_verify", {"skipped": True, "reason": str(e)})
            return JSONResponse(payload, status_code=resp.status_code)

        payload["grounded_verify"] = {
            "passed": verdict.passed,
            "violations": verdict.violations,
            "latency_ms": verdict.latency_ms,
        }
        if block_on_fail and not verdict.passed:
            return JSONResponse(
                {
                    "error": {
                        "message": "grounded verify failed",
                        "type": "grounded_verify_failed",
                        "violations": verdict.violations,
                    },
                    "grounded_verify": payload["grounded_verify"],
                },
                status_code=422,
            )
        return JSONResponse(payload, status_code=resp.status_code)

    async def _proxy_stream(request: Request, body: dict[str, Any], *, kind: str) -> StreamingResponse:
        headers = _forward_headers(request)
        path = "/v1/chat/completions" if kind == "chat" else "/v1/completions"
        context = extract_grounded_context(body)

        async def event_gen() -> AsyncIterator[bytes]:
            collected: list[str] = []
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                async with http.stream("POST", f"{upstream}{path}", headers=headers, json=body) as resp:
                    if resp.status_code >= 400:
                        yield await resp.aread()
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        raw = line if line.startswith("data:") else f"data: {line}"
                        payload_line = raw[5:].strip() if raw.startswith("data:") else raw
                        if payload_line == "[DONE]":
                            if verify_enabled and collected:
                                full = "".join(collected)
                                try:
                                    verdict = guardrails.verify_text(full, context=context)
                                    if block_on_fail and not verdict.passed:
                                        err = {
                                            "error": {
                                                "message": "grounded verify failed",
                                                "type": "grounded_verify_failed",
                                                "violations": verdict.violations,
                                            }
                                        }
                                        yield f"data: {json.dumps(err)}\n\n".encode()
                                        return
                                except grpc.RpcError as e:
                                    log.warning("final verify failed: %s", e)
                            yield b"data: [DONE]\n\n"
                            return
                        try:
                            chunk = json.loads(payload_line)
                        except json.JSONDecodeError:
                            yield (raw + "\n\n").encode()
                            continue
                        delta = stream_delta_text(chunk)
                        if delta and verify_enabled:
                            collected.append(delta)
                            try:
                                verdicts = guardrails.verify_stream_deltas([delta])
                                if block_on_fail and verdicts and verdicts[-1].action == "BLOCK":
                                    err = {
                                        "error": {
                                            "message": "grounded verify blocked stream",
                                            "type": "grounded_verify_blocked",
                                            "reason": verdicts[-1].reason,
                                            "matched_rules": verdicts[-1].matched_rules,
                                        }
                                    }
                                    yield f"data: {json.dumps(err)}\n\n".encode()
                                    return
                            except grpc.RpcError as e:
                                log.debug("stream verify skip: %s", e)
                        elif delta:
                            collected.append(delta)
                        yield (raw + "\n\n").encode()

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    def _forward_headers(request: Request) -> dict[str, str]:
        out = {"content-type": "application/json"}
        for key in PASS_THROUGH_HEADERS:
            val = request.headers.get(key)
            if val:
                out[key] = val
        return out

    return app


def _require_guardrails() -> bool:
    return os.environ.get("GROUNDED_VLLM_REQUIRE_GUARDRAILS", "").lower() in {"1", "true", "yes"}
