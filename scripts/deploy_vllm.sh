#!/usr/bin/env bash
#
# deploy_vllm.sh - Deploy vLLM in Docker with a Hugging Face model
#
# Usage: ./scripts/deploy_vllm.sh
#
set -euo pipefail

CONTAINER_NAME="vllm-instance"
VLLM_IMAGE="vllm/vllm-openai:latest"
MODELS_DIR="$(pwd)/models"
DEFAULT_PORT=8000

# ── 1. Check if Docker is installed and running ──────────────────────────────
echo "==> Checking Docker installation..."
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "ERROR: Docker daemon is not running. Start it and try again."
    exit 1
fi
echo "    Docker version: $(docker --version)"

# ── Check if vLLM is already deployed ────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "==> vLLM container '${CONTAINER_NAME}' is already running."
    echo "    To stop it:  docker stop ${CONTAINER_NAME}"
    echo "    To restart:  docker restart ${CONTAINER_NAME}"
    exit 0
fi

# ── 2. Ask which model the user wants to use ─────────────────────────────────
echo ""
echo "==> Select a model for deployment"
echo ""
echo "Recommended models for Spark DGX kits (NVIDIA GPU-accelerated):"
echo ""
printf "  %-4s  %-45s  %s\n" "#" "Model" "Description"
printf "  %-4s  %-45s  %s\n" "---" "---------------------------------------------" "--------------------"
printf "  %-4s  %-45s  %s\n" "1"  "meta-llama/Llama-3.3-70B-Instruct"       "Strong general-purpose LLM"
printf "  %-4s  %-45s  %s\n" "2"  "mistralai/Mistral-Large-Instruct-2407"   "High-quality multilingual model"
printf "  %-4s  %-45s  %s\n" "3"  "meta-llama/Llama-3.1-8B-Instruct"        "Fast, lightweight inference"
printf "  %-4s  %-45s  %s\n" "4"  "nvidia/Llama-3.1-Nemotron-70B-Instruct"  "Fine-tuned for quality & safety"
printf "  %-4s  %-45s  %s\n" "5"  "Qwen/Qwen2.5-72B-Instruct"               "Strong open-source multilingual model"
echo ""
echo "Other popular options:"
echo "  - deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
echo "  - google/gemma-2-27b-it"
echo "  - meta-llama/Llama-3.2-3B-Instruct"
echo ""

read -r -p "Enter model number [1-5] or paste a custom Hugging Face repo ID: " MODEL_CHOICE

case "${MODEL_CHOICE}" in
    1) HF_MODEL="meta-llama/Llama-3.3-70B-Instruct" ;;
    2) HF_MODEL="mistralai/Mistral-Large-Instruct-2407" ;;
    3) HF_MODEL="meta-llama/Llama-3.1-8B-Instruct" ;;
    4) HF_MODEL="nvidia/Llama-3.1-Nemotron-70B-Instruct" ;;
    5) HF_MODEL="Qwen/Qwen2.5-72B-Instruct" ;;
    *)
        # Allow custom model ID
        if [[ -z "${MODEL_CHOICE}" ]]; then
            echo "ERROR: No model selected."
            exit 1
        fi
        HF_MODEL="${MODEL_CHOICE}"
        ;;
esac

echo ""
echo "    Selected model: ${HF_MODEL}"

# ── 3. Download the model into the "models" folder ───────────────────────────
echo ""
echo "==> Downloading model '${HF_MODEL}' to ${MODELS_DIR} ..."

mkdir -p "${MODELS_DIR}"

if command -v huggingface-cli &>/dev/null; then
    # Use huggingface-cli directly (preferred, shows progress)
    huggingface-cli download \
        --resume-download \
        "${HF_MODEL}" \
        --local-dir "${MODELS_DIR}"
else
    # Fall back to Python + huggingface_hub
    if ! python3 -c "import huggingface_hub" &>/dev/null; then
        echo "    Installing huggingface_hub ..."
        pip install --quiet huggingface_hub
    fi
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    '${HF_MODEL}',
    local_dir='${MODELS_DIR}',
    resume_download=True,
)
"
fi

echo "    Model downloaded to ${MODELS_DIR}"

# ── 4. Deploy vLLM in Docker ────────────────────────────────────────────────
echo ""
echo "==> Pulling vLLM image '${VLLM_IMAGE}' ..."
docker pull "${VLLM_IMAGE}"

echo ""
echo "==> Starting vLLM container '${CONTAINER_NAME}' ..."
echo "    Model : ${HF_MODEL}"
echo "    Port  : ${DEFAULT_PORT}"
echo "    Models: ${MODELS_DIR} -> /app/models"
echo ""

docker run -d \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    -p "${DEFAULT_PORT}:${DEFAULT_PORT}" \
    -v "${MODELS_DIR}:/app/models" \
    -e HF_HUB_DISABLE_PROGRESS_BARS=1 \
    --env-file <(env | grep -i 'hf_\|huggingface' || true) \
    --shm-size=auto \
    "${VLLM_IMAGE}" \
    serve \
        /app/models \
        --host 0.0.0.0 \
        --port "${DEFAULT_PORT}" \
        --tensor-parallel-size auto

echo ""
echo "==> vLLM container '${CONTAINER_NAME}' is starting up ..."
echo ""
echo "    Check status:  docker ps | grep ${CONTAINER_NAME}"
echo "    View logs:     docker logs -f ${CONTAINER_NAME}"
echo "    Stop it:       docker stop ${CONTAINER_NAME}"
echo "    API endpoint:  http://localhost:${DEFAULT_PORT}/v1"
echo ""
echo "    Try a completion:"
echo "      curl -s http://localhost:${DEFAULT_PORT}/v1/completions \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d '{\"model\": \"\", \"prompt\": \"Hello, world!\", \"max_tokens\": 64}'"
echo ""
