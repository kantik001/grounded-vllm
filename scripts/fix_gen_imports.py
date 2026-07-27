"""Fix generated protobuf imports for package layout."""

from __future__ import annotations

from pathlib import Path

GEN = Path(__file__).resolve().parents[1] / "grounded_vllm" / "gen"


def main() -> None:
    grpc_file = GEN / "guardrails_pb2_grpc.py"
    text = grpc_file.read_text(encoding="utf-8")
    text = text.replace(
        "import guardrails_pb2 as guardrails__pb2",
        "from grounded_vllm.gen import guardrails_pb2 as guardrails__pb2",
    )
    grpc_file.write_text(text, encoding="utf-8")
    init = GEN / "__init__.py"
    if not init.exists():
        init.write_text('"""Generated gRPC stubs for grounded-guardrails."""\n', encoding="utf-8")
    print(f"fixed imports in {grpc_file}")


if __name__ == "__main__":
    main()
