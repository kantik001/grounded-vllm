from grounded_vllm.openai_util import (
    assistant_text_from_chat_completion,
    extract_grounded_context,
    stream_delta_text,
)
from grounded_vllm.logits_processor import GroundedAdapterLogitsProcessor


class _Params:
    def __init__(self, extra_args):
        self.extra_args = extra_args


def test_extract_grounded_context_from_extra_body():
    body = {"extra_body": {"grounded_context": "Revenue was 14."}}
    assert extract_grounded_context(body) == "Revenue was 14."


def test_extract_from_grounding_role():
    body = {"messages": [{"role": "grounding", "content": "ctx-1"}]}
    assert extract_grounded_context(body) == "ctx-1"


def test_assistant_and_delta_parsers():
    chat = {"choices": [{"message": {"content": "hello"}}]}
    assert assistant_text_from_chat_completion(chat) == "hello"
    chunk = {"choices": [{"delta": {"content": "hi"}}]}
    assert stream_delta_text(chunk) == "hi"


def test_logits_processor_validates_extra_args():
    GroundedAdapterLogitsProcessor.validate_params(_Params({"grounded_context": "ok"}))
    try:
        GroundedAdapterLogitsProcessor.validate_params(_Params({"grounded_context": 1}))
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_healthz():
    from fastapi.testclient import TestClient
    from grounded_vllm.proxy import create_app

    app = create_app(upstream="http://example.invalid", guardrails_addr="127.0.0.1:50052")
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
