#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$#" -gt 1 ]; then
    echo "Uso: sh avvia.sh [--gpu|--cpu]" >&2
    exit 1
fi
case "${1:-}" in
    --gpu) AROL_USE_GPU=1 ;;
    ""|--cpu) AROL_USE_GPU=0 ;;
    *) echo "Uso: sh avvia.sh [--gpu|--cpu]" >&2; exit 1 ;;
esac
compose() {
    if [ "$AROL_USE_GPU" = 1 ]; then
        docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml "$@"
    else
        docker compose -f compose.delivery.yml "$@"
    fi
}

if ! docker info >/dev/null 2>&1; then
    echo "Avvia Docker Desktop (o Docker Engine), poi ripeti questo comando." >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "Serve Docker Compose v2: aggiorna Docker Desktop o installa il plugin Compose." >&2
    exit 1
fi
set -- data/manuals/*.pdf
if [ ! -f "$1" ]; then
    echo "Mancano i manuali: copia i PDF del dataset in data/manuals, senza rinominarli." >&2
    exit 1
fi

# Check the Docker runtime before stopping any currently usable application.
if [ "$AROL_USE_GPU" = 1 ]; then
    echo "Modalita NVIDIA: verifica dell'accesso alla GPU dal container Ollama..."
    if ! compose run --rm --no-deps --entrypoint nvidia-smi ollama -L; then
        echo "GPU NVIDIA non accessibile a Docker. Consulta la sezione NVIDIA di CONSEGNA.md." >&2
        echo "Su Linux servono driver e NVIDIA Container Toolkit; su Windows Docker Desktop con WSL2." >&2
        exit 1
    fi
else
    echo "Modalita CPU. Per NVIDIA usa avvia-gpu.bat oppure sh avvia-gpu.sh."
fi

# Stop readers before the setup container updates the persistent Chroma index.
compose stop frontend backend agents
echo "Preparazione in corso: il primo avvio scarica i modelli e indicizza i manuali."
echo "Progresso in un altro terminale: docker compose -f compose.delivery.yml logs -f setup"
if ! compose up --build --wait --wait-timeout 7200; then
    compose logs --tail 30 setup
    echo "Avvio non completato. Consulta l'errore qui sopra e CONSEGNA.md." >&2
    exit 1
fi
echo "Pronto: http://localhost:${DELIVERY_APP_PORT:-8080}"
echo "Login app: elena.fabbri@valgrande.example / Arol2026!"
echo "Langfuse: http://localhost:${DELIVERY_LANGFUSE_PORT:-3000} (docente@arol.local / ArolDemo2026!)"
