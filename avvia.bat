@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
    echo Avvia Docker Desktop, poi esegui di nuovo questo file.
    goto :failed
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo Serve Docker Compose v2: aggiorna Docker Desktop.
    goto :failed
)
if not exist "data\manuals\*.pdf" (
    echo Mancano i manuali: copia i PDF del dataset in data\manuals, senza rinominarli.
    goto :failed
)
docker compose -f compose.delivery.yml stop frontend backend agents
if errorlevel 1 goto :failed
echo Preparazione in corso: il primo avvio scarica i modelli e indicizza i manuali.
echo Progresso in un altro terminale: docker compose -f compose.delivery.yml logs -f setup
docker compose -f compose.delivery.yml up --build --wait --wait-timeout 7200
if errorlevel 1 (
    docker compose -f compose.delivery.yml logs --tail 30 setup
    goto :failed
)
if not defined DELIVERY_APP_PORT set DELIVERY_APP_PORT=8080
if not defined DELIVERY_LANGFUSE_PORT set DELIVERY_LANGFUSE_PORT=3000
echo Pronto: http://localhost:%DELIVERY_APP_PORT%
echo Login app: elena.fabbri@valgrande.example / Arol2026!
echo Langfuse: http://localhost:%DELIVERY_LANGFUSE_PORT% (docente@arol.local / ArolDemo2026!)
start "" "http://localhost:%DELIVERY_APP_PORT%"
pause
exit /b 0
:failed
echo Avvio non completato. Consulta CONSEGNA.md e i log di Docker.
pause
exit /b 1
