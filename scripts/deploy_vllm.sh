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

# ── 1b. Set up Python virtual environment ────────────────────────────────────
VENV_DIR="$(pwd)/.venv"

if [[ ! -d "${VENV_DIR}" ]]; then
    echo ""
    echo "==> Creating Python virtual environment in ${VENV_DIR} ..."
    python3 -m venv "${VENV_DIR}"
fi

echo "==> Activating virtual environment ..."
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo "    Python: $(python --version)"
echo "    Pip:    $(pip --version)"

# Install huggingface_hub inside the venv if not already present
if ! python -c "import huggingface_hub" &>/dev/null; then
    echo ""
    echo "==> Installing huggingface_hub in virtual environment ..."
    pip install --quiet huggingface_hub
fi

# ── Check if vLLM container already exists ───────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Container exists — check its status
    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null)

    case "${CONTAINER_STATUS}" in
        running)
            echo "==> vLLM container '${CONTAINER_NAME}' is already running."
            read -r -p "    Do you want to restart it? [y/N] " RESTART_CHOICE
            if [[ "${RESTART_CHOICE}" =~ ^[Yy]$ ]]; then
                echo "    Stopping existing container..."
                docker stop "${CONTAINER_NAME}"
                echo "    Container stopped. Proceeding with fresh deployment..."
            else
                echo "    Skipping deployment. Container is running."
                exit 0
            fi
            ;;
        exited|created|paused|restarting|removing|dead)
            echo "==> vLLM container '${CONTAINER_NAME}' exists but is ${CONTAINER_STATUS}."
            read -r -p "    Start the existing container? [Y/n] " START_CHOICE
            if [[ "${START_CHOICE}" =~ ^[Nn]$ ]]; then
                echo "    Removing old container and proceeding with fresh deployment..."
                docker rm "${CONTAINER_NAME}"
            else
                echo "    Starting container '${CONTAINER_NAME}'..."
                docker start "${CONTAINER_NAME}"
                echo ""
                echo "==> vLLM container is starting up."
                echo ""
                echo "    Check status:  docker ps | grep ${CONTAINER_NAME}"
                echo "    View logs:     docker logs -f ${CONTAINER_NAME}"
                echo "    Stop it:       docker stop ${CONTAINER_NAME}"
                echo ""
                exit 0
            fi
            ;;
    esac
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

if command -v hf &>/dev/null; then
    # Use `hf` CLI (preferred, shows progress)
    hf download \
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
    --shm-size=8g \
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
