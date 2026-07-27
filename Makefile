.PHONY: proto test serve ci

proto:
	python -m grpc_tools.protoc \
	  -I proto \
	  --python_out=grounded_vllm/gen \
	  --grpc_python_out=grounded_vllm/gen \
	  proto/guardrails.proto
	python scripts/fix_gen_imports.py

test:
	python -m pytest -q

serve:
	python -m grounded_vllm serve --upstream http://127.0.0.1:8000 --guardrails 127.0.0.1:50052 --port 8001

ci: test
