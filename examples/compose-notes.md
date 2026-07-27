# Example: wire grounded-llm → grounded-vllm → vLLM

```bash
# 1) guardrails
cd ../grounded-guardrails/go && go run ./cmd/server

# 2) vLLM (GPU host)
vllm serve $VLLM_MODEL --host 0.0.0.0 --port 8000

# 3) adapter
grounded-vllm serve --upstream http://127.0.0.1:8000 --guardrails 127.0.0.1:50052 --port 8001

# 4) grounded-llm .env
# LLM_PROVIDER=vllm
# LLM_BASE_URL=http://127.0.0.1:8001/v1
```
