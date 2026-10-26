#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

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

# Stop readers before the setup container updates the persistent Chroma index.
docker compose -f compose.delivery.yml stop frontend backend agents
echo "Preparazione in corso: il primo avvio scarica i modelli e indicizza i manuali."
echo "Progresso in un altro terminale: docker compose -f compose.delivery.yml logs -f setup"
if ! docker compose -f compose.delivery.yml up --build --wait --wait-timeout 7200; then
    docker compose -f compose.delivery.yml logs --tail 30 setup
    echo "Avvio non completato. Consulta l'errore qui sopra e CONSEGNA.md." >&2
    exit 1
fi
echo "Pronto: http://localhost:${DELIVERY_APP_PORT:-8080}"
echo "Login app: elena.fabbri@valgrande.example / Arol2026!"
echo "Langfuse: http://localhost:${DELIVERY_LANGFUSE_PORT:-3000} (docente@arol.local / ArolDemo2026!)"
