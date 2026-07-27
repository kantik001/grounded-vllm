"""Optional vLLM logits-processor entry point.

Numeric / PII verify needs *decoded text*, so this processor does not call
guardrails inside apply() (that would be wrong and too slow).

It validates SamplingParams.extra_args so callers can attach grounded_context
for the OpenAI proxy / future post-generation hooks (see UPSTREAM.md).

When vLLM is not installed, the class remains importable for entry-point
discovery without breaking non-vLLM installs.
"""

from __future__ import annotations

from typing import Any

try:
    from vllm.v1.sample.logits_processor import AdapterLogitsProcessor
except ImportError:  # pragma: no cover - exercised only with vLLM installed
    AdapterLogitsProcessor = object  # type: ignore[misc,assignment]


class GroundedAdapterLogitsProcessor(AdapterLogitsProcessor):  # type: ignore[misc]
    """No-op logits adapter that validates grounded_* extra_args."""

    @classmethod
    def validate_params(cls, params: Any) -> None:
        extra = getattr(params, "extra_args", None) or {}
        if not isinstance(extra, dict):
            return
        ctx = extra.get("grounded_context")
        if ctx is not None and not isinstance(ctx, str):
            raise ValueError("extra_args.grounded_context must be a string")
        flag = extra.get("grounded_verify")
        if flag is not None and not isinstance(flag, bool):
            raise ValueError("extra_args.grounded_verify must be a bool")

    def is_argmax_invariant(self) -> bool:
        return True

    def new_req_logits_processor(self, params: Any) -> None:
        # Disabled per-request: verify runs in grounded-vllm proxy / post-hooks.
        return None
