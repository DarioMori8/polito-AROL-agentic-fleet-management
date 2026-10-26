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
    echo Start Docker Desktop, then run this file again.
    goto :failed
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo Docker Compose v2 is required: update Docker Desktop.
    goto :failed
)
if not exist "data\manuals\*.pdf" (
    echo Manuals missing: copy the dataset PDFs into data\manuals, without renaming them.
    goto :failed
)
if "%AROL_USE_GPU%"=="1" (
    echo NVIDIA mode: checking GPU access from the Ollama container...
    docker compose %AROL_COMPOSE_FILES% run --rm --no-deps --entrypoint nvidia-smi ollama -L
    if errorlevel 1 (
        echo NVIDIA GPU not accessible to Docker. See the NVIDIA section of DELIVERY.md.
        echo Windows needs up-to-date NVIDIA drivers and Docker Desktop with WSL2.
        goto :failed
    )
) else (
    echo CPU mode. For NVIDIA use avvia-gpu.bat.
)
docker compose %AROL_COMPOSE_FILES% stop frontend backend agents
if errorlevel 1 goto :failed
echo Preparing: the first start downloads the models and indexes the manuals.
echo Progress in another terminal: docker compose -f compose.delivery.yml logs -f setup
docker compose %AROL_COMPOSE_FILES% up --build --wait --wait-timeout 7200
if errorlevel 1 (
    docker compose %AROL_COMPOSE_FILES% logs --tail 30 setup
    goto :failed
)
if not defined DELIVERY_APP_PORT set DELIVERY_APP_PORT=8080
if not defined DELIVERY_LANGFUSE_PORT set DELIVERY_LANGFUSE_PORT=3000
echo Ready: http://localhost:%DELIVERY_APP_PORT%
echo Login app: elena.fabbri@valgrande.example / Arol2026!
echo Langfuse: http://localhost:%DELIVERY_LANGFUSE_PORT% (docente@arol.local / ArolDemo2026!)
start "" "http://localhost:%DELIVERY_APP_PORT%"
pause
exit /b 0
:usage
echo Usage: avvia.bat [--gpu^|--cpu]
goto :failed
:failed
echo Start not completed. See DELIVERY.md and the Docker logs.
pause
exit /b 1
