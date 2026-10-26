@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "AROL_COMPOSE_FILES=-f compose.delivery.yml"
set "AROL_USE_GPU=0"
if not "%~2"=="" goto :usage
if "%~1"=="" goto :options_ready
if /I "%~1"=="--cpu" goto :options_ready
if /I not "%~1"=="--gpu" goto :usage
set "AROL_COMPOSE_FILES=-f compose.delivery.yml -f compose.delivery.gpu.yml"
set "AROL_USE_GPU=1"
:options_ready
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
if "%AROL_USE_GPU%"=="1" (
    echo Modalita NVIDIA: verifica dell'accesso alla GPU dal container Ollama...
    docker compose %AROL_COMPOSE_FILES% run --rm --no-deps --entrypoint nvidia-smi ollama -L
    if errorlevel 1 (
        echo GPU NVIDIA non accessibile a Docker. Consulta la sezione NVIDIA di CONSEGNA.md.
        echo Su Windows servono driver NVIDIA aggiornati e Docker Desktop con WSL2.
        goto :failed
    )
) else (
    echo Modalita CPU. Per NVIDIA usa avvia-gpu.bat.
)
docker compose %AROL_COMPOSE_FILES% stop frontend backend agents
if errorlevel 1 goto :failed
echo Preparazione in corso: il primo avvio scarica i modelli e indicizza i manuali.
echo Progresso in un altro terminale: docker compose -f compose.delivery.yml logs -f setup
docker compose %AROL_COMPOSE_FILES% up --build --wait --wait-timeout 7200
if errorlevel 1 (
    docker compose %AROL_COMPOSE_FILES% logs --tail 30 setup
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
:usage
echo Uso: avvia.bat [--gpu^|--cpu]
goto :failed
:failed
echo Avvio non completato. Consulta CONSEGNA.md e i log di Docker.
pause
exit /b 1
