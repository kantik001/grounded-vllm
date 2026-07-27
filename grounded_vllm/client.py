"""gRPC client for grounded-guardrails (:50052)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import grpc

from grounded_vllm.gen import guardrails_pb2, guardrails_pb2_grpc


@dataclass(frozen=True)
class TextVerdict:
    passed: bool
    violations: list[str]
    latency_ms: float


@dataclass(frozen=True)
class StreamVerdict:
    action: str  # PASS | BLOCK | FLAG
    reason: str
    matched_rules: list[str]
    latency_ms: float


class GuardrailsClient:
    """Thin unary + streaming client for GuardrailsService."""

    def __init__(self, address: str = "127.0.0.1:50052", *, timeout_s: float = 2.0):
        self.address = address
        self.timeout_s = timeout_s
        self._channel = grpc.insecure_channel(address)
        self._stub = guardrails_pb2_grpc.GuardrailsServiceStub(self._channel)

    def close(self) -> None:
        self._channel.close()

    def __enter__(self) -> GuardrailsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def verify_text(
        self,
        text: str,
        *,
        context: str = "",
        tenant_id: str = "",
        rules: list[str] | None = None,
    ) -> TextVerdict:
        req = guardrails_pb2.TextRequest(
            text=text,
            context=context or "",
            tenant_id=tenant_id or "",
            rules=rules or [],
        )
        resp = self._stub.VerifyText(req, timeout=self.timeout_s)
        return TextVerdict(
            passed=bool(resp.passed),
            violations=list(resp.violations),
            latency_ms=float(resp.latency_ms),
        )

    def verify_stream_deltas(
        self,
        deltas: Iterable[str],
        *,
        tenant_id: str = "",
        session_id: str = "",
    ) -> list[StreamVerdict]:
        def _gen():
            for delta in deltas:
                yield guardrails_pb2.TokenBatch(
                    text_delta=delta,
                    tenant_id=tenant_id or "",
                    session_id=session_id or "",
                )

        out: list[StreamVerdict] = []
        for resp in self._stub.VerifyStream(_gen(), timeout=self.timeout_s):
            action = guardrails_pb2.Verdict.Action.Name(resp.action)
            out.append(
                StreamVerdict(
                    action=action,
                    reason=resp.reason or "",
                    matched_rules=list(resp.matched_rules),
                    latency_ms=float(resp.latency_ms),
                )
            )
        return out
