#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$#" -gt 1 ]; then
    echo "Usage: sh avvia.sh [--gpu|--cpu]" >&2
    exit 1
fi
case "${1:-}" in
    --gpu) AROL_USE_GPU=1 ;;
    ""|--cpu) AROL_USE_GPU=0 ;;
    *) echo "Usage: sh avvia.sh [--gpu|--cpu]" >&2; exit 1 ;;
esac
compose() {
    if [ "$AROL_USE_GPU" = 1 ]; then
        docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml "$@"
    else
        docker compose -f compose.delivery.yml "$@"
    fi
}

if ! docker info >/dev/null 2>&1; then
    echo "Start Docker Desktop (or Docker Engine), then run this command again." >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is required: update Docker Desktop or install the Compose plugin." >&2
    exit 1
fi
set -- data/manuals/*.pdf
if [ ! -f "$1" ]; then
    echo "Manuals missing: copy the dataset PDFs into data/manuals, without renaming them." >&2
    exit 1
fi

# Check the Docker runtime before stopping any currently usable application.
if [ "$AROL_USE_GPU" = 1 ]; then
    echo "NVIDIA mode: checking GPU access from the Ollama container..."
    if ! compose run --rm --no-deps --entrypoint nvidia-smi ollama -L; then
        echo "NVIDIA GPU not accessible to Docker. See the NVIDIA section of SETUP.md." >&2
        echo "Linux needs drivers and the NVIDIA Container Toolkit; Windows needs Docker Desktop with WSL2." >&2
        exit 1
    fi
else
    echo "CPU mode. For NVIDIA use avvia-gpu.bat or sh avvia-gpu.sh."
fi

# Stop readers before the setup container updates the persistent Chroma index.
compose stop frontend backend agents
echo "Preparing: the first start downloads the models and indexes the manuals."
echo "Progress in another terminal: docker compose -f compose.delivery.yml logs -f setup"
if ! compose up --build --wait --wait-timeout 7200; then
    compose logs --tail 30 setup
    echo "Start not completed. See the error above and SETUP.md." >&2
    exit 1
fi
echo "Ready: http://localhost:${DELIVERY_APP_PORT:-8080}"
echo "Login app: elena.fabbri@valgrande.example / Arol2026!"
echo "Langfuse: http://localhost:${DELIVERY_LANGFUSE_PORT:-3000} (docente@arol.local / ArolDemo2026!)"
