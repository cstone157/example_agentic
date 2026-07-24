# Plan: LangChain/LangGraph with Local Model on NVIDIA DGX

## Overview

This plan describes how to adapt the multi-agent workflow (from `PLAN.md`) to use **locally-hosted LLMs** on an **NVIDIA DGX** system instead of cloud APIs (OpenAI, etc.). The DGX provides the GPU compute needed for high-throughput inference across multiple agents running in parallel.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    NVIDIA DGX INFRASTRUCTURE                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Local LLM Inference Server                       │   │
│  │                                                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │   │
│  │  │ vLLM /       │  │ Ollama /     │  │ TGI (Text          │  │   │
│  │  │ TensorRT-LLM │  │ LM Studio    │  │ Generation         │  │   │
│  │  │              │  │              │  │ Server)            │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬───────────┘  │   │
│  │         └────────────────┼──────────────────┘              │   │
│  │                          │ HTTP / REST                       │   │
│  │                     (localhost:8000)                         │   │
│  └─────────────────────────┼──────────────────────────────────┘   │
│                            │                                       │
│  ┌─────────────────────────▼──────────────────────────────────┐   │
│  │              LangChain / LangGraph Pipeline                 │   │
│  │                                                              │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │   │
│  │  │Planner │→  │Tasker  │→  │Coder   │→  │Tester   │          │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘           │   │
│  │       ▲                                     │               │   │
│  │       └─────── (loop on failure) ───────────┘               │   │
│  │                                                              │   │
│  │  LangChain ChatModel → local OpenAI-compatible endpoint     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│              spark-dgx (NVIDIA DGX Server)                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Local Model Selection & Preparation

### 1.1 Model Candidates for Code Generation

| Model | Parameters | License | Strengths | GPU Memory Required |
|-------|-----------|---------|-----------|---------------------|
| **Codestral** | 22B | Mistral Community | Excellent code generation, multilingual | ~14 GB (FP16) |
| **DeepSeek Coder V2** | 236B (MoE) | Apache 2.0 | State-of-the-art coding | ~48 GB (INT4) / ~96 GB (FP16) |
| **Qwen 2.5 Coder** | 32B | Apache 2.0 | Strong Python/code, fast inference | ~20 GB (FP16) |
| **Llama 3.1** | 70B | Meta License | General-purpose, strong reasoning | ~140 GB (FP16) / ~40 GB (INT4) |
| **Mistral Large** | 123B | Custom | Strong planning & architecture | ~240 GB (FP16) |

### 1.2 Recommended Stack for spark-dgx

```
Primary Model:  Qwen 2.5 Coder 32B  (best balance of quality/speed/memory)
Fallback Model: Codestral 22B       (faster, lighter tasks)
Reasoning:      Llama 3.1 70B       (complex planning/architecture tasks)
```

The DGX typically has 8× A100/H100 GPUs — this is sufficient to run multiple models simultaneously or use tensor parallelism for larger models.

### 1.3 Model Download & Quantization

```bash
# Using Hugging Face CLI
pip install huggingface_hub
huggingface-cli download Qwen/Qwen2.5-Coder-32B-Instruct --local-dir ./models/qwen-coder-32b

# Quantize with bitsandbytes (INT4) for reduced memory footprint
# or use GGUF format with llama.cpp / Ollama
pip install optimum[neural-compressor]
```

---

## Phase 2: Inference Server Setup on spark-dgx

### 2.1 Option A — vLLM (Recommended for throughput)

vLLM provides PagedAttention, continuous batching, and tensor parallelism — ideal for serving multiple agents concurrently.

```dockerfile
# Dockerfile for vLLM inference server
FROM vllm/vllm-runtime:latest

ENV VLLM_HOST_IP=0.0.0.0
ENV PORT=8000

COPY models/ /data/models/
```

```bash
# Launch vLLM with tensor parallelism across DGX GPUs
docker run --gpus all \
  -p 8000:8000 \
  -v ./models:/data/models \
  vllm/vllm-runtime:latest \
  --model /data/models/qwen-coder-32b \
  --tensor-parallel-size 4 \
  --max-model-len 16384 \
  --host 0.0.0.0 \
  --port 8000
```

### 2.2 Option B — Ollama (Simpler, single-model)

```bash
# Install Ollama on spark-dgx
curl -fsSL https://ollama.com/install.sh | sh

# Pull and serve the model
ollama pull qwen2.5-coder:32b
ollama serve --host 0.0.0.0

# Model runs at http://spark-dgx:11434
```

### 2.3 Option C — NVIDIA TGI (Text Generation Inference)

```bash
# Using NVIDIA's TGI container
docker run --gpus all \
  -p 8080:80 \
  -v ./models:/data/models \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id Qwen/Qwen2.5-Coder-32B-Instruct \
  --sharded true \
  --num-shard 4 \
  --max-batch-total-tokens 65536
```

### 2.4 Inference Server Comparison

| Feature | vLLM | Ollama | TGI |
|---------|------|--------|-----|
| Multi-GPU tensor parallelism | ✅ | ❌ | ✅ |
| OpenAI-compatible API | ✅ | ✅ | ❌ (native) |
| Continuous batching | ✅ | ❌ | ✅ |
| Easy setup | Medium | Easiest | Hard |
| Throughput | Highest | Moderate | High |
| Model variety | Broad | Good | HuggingFace only |

**Recommendation: vLLM** for the DGX — it maximizes GPU utilization and provides an OpenAI-compatible API that LangChain uses natively.

---

## Phase 3: LangChain Integration with Local Model

### 3.1 Dependencies (`requirements.txt`)

```txt
langchain>=0.3.0
langchain-openai>=0.2.0          # Reused for local OpenAI-compatible endpoints
langgraph>=0.2.0
vllm                             # Optional: direct vLLM client
transformers>=4.44.0             # For model loading if not using server
torch>=2.4.0                     # PyTorch backend
accelerate>=0.34.0               # Model loading utilities
```

### 3.2 Local LLM Client (`src/agents/llm_client.py`)

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional


class LocalLLMClient:
    """LangChain-compatible client for local models on spark-dgx."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-Coder-32B-Instruct",
        base_url: str = "http://spark-dgx:8000/v1",  # vLLM OpenAI endpoint
        api_key: str = "sk-no-key-required",           # vLLM requires this placeholder
        temperature: float = 0.2,                      # Low temp for code generation
        max_tokens: int = 4096,
        timeout: int = 120,
    ):
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def invoke(self, messages: list) -> str:
        """Send messages and return the model's response."""
        response = self.llm.invoke(messages)
        return response.content

    def invoke_with_stream(self, messages: list):
        """Stream responses for real-time feedback."""
        return self.llm.stream(messages)


# Factory for different agent roles with tuned parameters
def create_planner_client() -> LocalLLMClient:
    """Planner needs high reasoning — use higher temperature."""
    return LocalLLMClient(temperature=0.4, max_tokens=8192)


def create_coder_client() -> LocalLLMClient:
    """Coder needs precision — low temperature."""
    return LocalLLMClient(temperature=0.1, max_tokens=4096)


def create_tester_client() -> LocalLLMClient:
    """Tester needs analytical thinking."""
    return LocalLLMClient(temperature=0.2, max_tokens=4096)
```

### 3.3 Node Implementation with Local LLM (`src/workflow/nodes.py`)

```python
from src.workflow.state import AppWorkflowState
from src.agents.llm_client import create_planner_client, create_coder_client, create_tester_client


def run_planner(state: AppWorkflowState) -> dict:
    """Call planner agent using local model on spark-dgx."""
    client = create_planner_client()

    messages = [
        SystemMessage(content="You are a senior software architect. Analyze the application description and produce a structured implementation plan."),
        HumanMessage(content=state["app_description"]),
    ]

    response = client.invoke(messages)
    # Parse response into plan, stories, tech_stack (use regex/JSON parsing)
    parsed = parse_planner_response(response)

    return {
        "implementation_plan": parsed["plan"],
        "user_stories": parsed["stories"],
        "tech_stack": parsed["tech_stack"],
        "status": "drafting",
    }


def run_coder(state: AppWorkflowState) -> dict:
    """Call coder agent using local model on spark-dgx."""
    client = create_coder_client()

    messages = [
        SystemMessage(content="You are a senior Python developer. Write production-quality code."),
        HumanMessage(content=f"Tasks:\n{state['tasks']}\n\nPlan context:\n{state['implementation_plan']}"),
    ]

    response = client.invoke(messages)
    parsed = parse_coder_response(response)  # Extract {filepath: code}

    written = write_files(parsed["files"])
    return {
        "generated_code": parsed["files"],
        "code_files_written": written,
        "status": "testing",
    }


# ... tester and security nodes follow the same pattern
```

---

## Phase 4: LangGraph State Machine (Unchanged from PLAN.md)

The LangGraph state definition (`state.py`) and graph compilation (`graph.py`) remain **identical** to `PLAN.md`. The only change is that each node now calls `LocalLLMClient` instead of an OpenAI API.

```python
# graph.py — same structure, different node implementations
from langgraph.graph import StateGraph, START, END
from src.workflow.state import AppWorkflowState
from src.workflow.nodes import run_planner, run_tasker, run_coder, run_tester, run_security_scanner

workflow = StateGraph(AppWorkflowState)
workflow.add_node("planner", run_planner)
workflow.add_node("tasker", run_tasker)
workflow.add_node("coder", run_coder)
workflow.add_node("tester", run_tester)
workflow.add_node("security", run_security_scanner)

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "tasker")
workflow.add_edge("tasker", "coder")
workflow.add_edge("coder", "tester")
workflow.add_conditional_edges(
    "tester",
    should_fix_code,
    {"coder": "coder", "security": "security"},
)
workflow.add_edge("security", END)

app_graph = workflow.compile()
```

---

## Phase 5: spark-dgx Infrastructure Setup

### 5.1 DGX Configuration Checklist

```bash
# 1. Verify GPU availability and memory
nvidia-smi

# 2. Check CUDA version
nvcc --version

# 3. Install Docker with GPU support
sudo apt install docker.io
sudo usermod -aG docker $USER
newgrp docker

# 4. Install NVIDIA Container Toolkit (for GPU-in-Docker)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker

# 5. Restart Docker
sudo systemctl restart docker

# 6. Verify GPU access in containers
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### 5.2 Environment Variables (`.env`)

```bash
# spark-dgx inference server
VLLM_BASE_URL=http://spark-dgx:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
VLLM_API_KEY=sk-no-key-required

# Alternative: Ollama endpoint
OLLAMA_BASE_URL=http://spark-dgx:11434/v1

# Model tuning
MODEL_TEMPERATURE=0.2
MODEL_MAX_TOKENS=4096
MODEL_TIMEOUT=120

# Workflow control
MAX_CODING_LOOPS=5          # Prevent infinite coder↔tester loops
TEST_FAILURE_THRESHOLD=3    # Max test retry attempts before failing
```

### 5.3 Docker Compose for Full Pipeline

```yaml
version: '3.8'

services:
  inference-server:
    image: vllm/vllm-runtime:latest
    container_name: spark-dgx-inference
    runtime: nvidia
    ports:
      - "8000:8000"
    volumes:
      - ./models:/data/models:ro
    command: >
      --model /data/models/qwen-coder-32b
      --tensor-parallel-size 4
      --max-model-len 16384
      --host 0.0.0.0
      --port 8000
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 4
              capabilities: [gpu]
    restart: unless-stopped

  workflow-runner:
    build: .
    container_name: agentic-workflow
    depends_on:
      - inference-server
    environment:
      - VLLM_BASE_URL=http://inference-server:8000/v1
      - MODEL_TEMPERATURE=0.2
      - MAX_CODING_LOOPS=5
    volumes:
      - ./output:/app/output   # Generated code output
    restart: "no"

  trivy-scan:
    image: aquasec/trivy:latest
    container_name: trivy-scanner
    volumes:
      - ./output:/app:ro
    command: >
      image
      --format json
      --severity CRITICAL,HIGH,MEDIUM
      --exit-code 0
      /app
```

---

## Phase 6: Performance Optimization on DGX

### 6.1 Tensor Parallelism Strategy

```
DGX with 8× A100 (80GB each):
├── Model partitioned across 4 GPUs (tensor_parallel_size=4)
├── Remaining 4 GPUs available for:
│   ├── Secondary model (Codestral 22B on 1 GPU)
│   ├── Batch inference queue
│   └── Future expansion
```

### 6.2 Quantization Options

| Format | Tool | Quality Impact | Memory Savings |
|--------|------|---------------|----------------|
| INT4 | bitsandbytes / GPTQ | Minimal for coding | ~75% |
| INT8 | AWQ | Negligible | ~50% |
| FP8 | NVIDIA TensorRT-LLM | Very small | ~50% |
| GGUF (Q4_K_M) | llama.cpp | Small | ~65% |

```bash
# Quantize with GPTQ using auto-gptq
pip install auto-gptq transformers
python quantize.py \
  --model_id Qwen/Qwen2.5-Coder-32B-Instruct \
  --bits 4 \
  --group_size 128 \
  --output_dir ./models/qwen-coder-32b-int4
```

### 6.3 Throughput Tuning

```python
# vLLM performance knobs
config = {
    "tensor_parallel_size": 4,       # GPUs for model
    "max_model_len": 16384,          # Context window
    "max_num_batched_tokens": 32768, # Tokens per batch
    "gpu_memory_utilization": 0.95,  # GPU VRAM usage target
    "swap_space": 16,                # CPU swap (GB) for overflow
    "enable_chunked_cache": True,    # Improve throughput for long prompts
}
```

---

## Phase 7: Testing & Validation

### 7.1 Local Model Health Check

```python
# tests/test_local_llm.py
import pytest
from src.agents.llm_client import LocalLLMClient


def test_model_connectivity():
    """Verify the local model on spark-dgx is reachable."""
    client = LocalLLMClient()
    response = client.invoke([
        {"role": "user", "content": "Say 'hello' in one word."}
    ])
    assert len(response.strip()) > 0


def test_code_generation_quality():
    """Verify the model can generate valid Python."""
    client = LocalLLMClient(temperature=0.1)
    response = client.invoke([
        {"role": "user", "content": "Write a Python function that computes Fibonacci numbers iteratively."}
    ])
    assert "def" in response
    assert "return" in response


def test_planner_response_structure():
    """Verify planner produces structured output."""
    client = LocalLLMClient(temperature=0.4)
    response = client.invoke([
        {"role": "user", "content": "Build a REST API for a todo list with SQLite."}
    ])
    assert "plan" in response.lower() or "architecture" in response.lower()
```

### 7.2 End-to-End Workflow Test

```python
# tests/test_workflow.py
from src.workflow.graph import app_graph
from src.workflow.state import AppWorkflowState


def test_full_workflow():
    """Run the complete agentic pipeline with a simple task."""
    initial_state: AppWorkflowState = {
        "app_description": "Build a Flask REST API that stores and retrieves notes in SQLite.",
        "messages": [],
        "status": "planning",
    }

    result = app_graph.invoke(initial_state)

    assert result["implementation_plan"]
    assert result["tasks"]
    assert result["generated_code"]
    assert result["code_files_written"]
    assert result.get("tests_passed", False) is True
```

---

## Phase 8: Implementation Roadmap

### Sprint 1 — Infrastructure (Week 1)
- [ ] Provision spark-dgx environment (CUDA, Docker, NVIDIA Container Toolkit)
- [ ] Download and quantize Qwen 2.5 Coder 32B model
- [ ] Deploy vLLM inference server with tensor parallelism
- [ ] Validate OpenAI-compatible endpoint at `http://spark-dgx:8000/v1`

### Sprint 2 — LangChain Integration (Week 2)
- [ ] Implement `LocalLLMClient` wrapper in `src/agents/llm_client.py`
- [ ] Create model factory functions for each agent role
- [ ] Write health-check and quality tests (`tests/test_local_llm.py`)
- [ ] Integrate with existing LangGraph state machine

### Sprint 3 — Agent Nodes (Week 3)
- [ ] Implement `run_planner` node with local LLM
- [ ] Implement `run_tasker` node with local LLM
- [ ] Implement `run_coder` node with local LLM + file write tool
- [ ] Implement `run_tester` node with local LLM + pytest runner

### Sprint 4 — Security & Polish (Week 4)
- [ ] Implement `run_security_scanner` node (Trivy)
- [ ] Add conditional retry logic (coder ↔ tester loop)
- [ ] Build Docker Compose for full pipeline
- [ ] Write end-to-end integration tests
- [ ] Document setup and usage in README.md

---

## Risk Assessment & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Local model produces lower-quality code than GPT-4 | Medium | Medium | Use 32B+ models; add iterative refinement loops; fallback to cloud API for critical tasks |
| vLLM server crashes under load | High | Low | Run health checks between nodes; implement retry with exponential backoff |
| GPU memory exhaustion with large context | High | Medium | Set `max_model_len` conservatively; use quantized models; chunk long prompts |
| spark-dgx network latency from client | Medium | Low | Run workflow runner on the same DGX host or in the same cluster |
| Model license restrictions for commercial use | Medium | Low | Use Apache 2.0 licensed models (Qwen, DeepSeek Coder) |

---

## Summary

This plan adapts the existing LangGraph multi-agent workflow to run entirely on a **local model hosted on spark-dgx**. The key changes from `PLAN.md` are:

1. **Replace cloud LLM calls** with `LocalLLMClient` pointing to a vLLM server on spark-dgx
2. **Select appropriate models** (Qwen 2.5 Coder 32B recommended) that fit the DGX GPU memory
3. **Deploy an inference server** (vLLM recommended) with tensor parallelism across DGX GPUs
4. **Add infrastructure setup steps** for Docker + NVIDIA Container Toolkit on spark-dgx
5. **Include performance tuning** (quantization, tensor parallelism, throughput knobs)

All LangGraph state machine logic, agent definitions, and workflow structure from `PLAN.md` remain unchanged — only the LLM backend is swapped from cloud to local.
