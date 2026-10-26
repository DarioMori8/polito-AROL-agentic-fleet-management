# AROL Fleet Management — delivery guide

## Quick start for the instructor

1. **Install and open [Docker Desktop](https://www.docker.com/products/docker-desktop/)**. On Linux, Docker Engine with Docker Compose v2 also works. Wait until Docker is running.
   Make sure Docker has **at least 16 GB of RAM** assigned. On installations that show the limit in Docker Desktop: **Settings → Resources → Advanced → Memory**, then apply and restart. With WSL2, the virtual machine memory is configured in the WSL settings. The computer's total RAM and the RAM assigned to Docker are two different values.
2. **Extract the whole ZIP package** into a local folder. The PDFs must already be in `data/manuals/`.
3. **Start the project**:
   - **Windows:** double-click `avvia.bat` in the extracted folder.
   - **macOS/Linux:** open a terminal in the extracted folder and run `sh avvia.sh`.
   - **With an NVIDIA GPU on Windows/Linux:** after the [GPU prerequisites](#optional-nvidia-gpu), use `avvia-gpu.bat` on Windows or `sh avvia-gpu.sh` on Linux instead.
4. Wait for the **Ready** message, then open **[http://localhost:8080](http://localhost:8080)**.

Application credentials:

| Field | Value |
|---|---|
| Email | `elena.fabbri@valgrande.example` |
| Password | `Arol2026!` |

There is no need to install Python, Node.js or Ollama on the computer, nor to create a `.env` file, cloud accounts or API keys. An Internet connection is needed on the first start to download images, dependencies and models. After that, inference and manual searches run locally.

**The first start can take several minutes**, mostly for downloading and indexing. The time depends on connection, CPU and memory. Do not close Docker during the preparation. The scripts wait up to two hours; if the wait times out, check the logs before running them again.

## Computer requirements

- Up-to-date Docker Desktop, or Docker Engine with Compose v2, on x86-64 or ARM64.
- Recommended budget for the whole stack: **at least 16 GB of RAM assigned to Docker**, so preferably a computer with 24–32 GB of RAM. This is a conservative estimate, not a minimum certified on every hardware.
- About **25 GB of free disk space** for images, models, build cache and data; usage can grow with conversations and traces.
- Ports **8080** and **3000** free on the computer.

The infrastructure service images are pinned by digest in the Compose file, so the tested versions are reused.

The default configuration uses the CPU and does not require GPU drivers. On CPU, answers can take minutes, since one answer may involve several model calls. On macOS, Docker does not expose Metal acceleration to Ollama: for a faster demo on a Mac, the development environment with native Ollama is also available, described in the [README](README.md). [Ollama reference](https://docs.ollama.com/faq).

**Mind the demo timing:** in the test on a Mac ARM64 with 16 GB assigned to Docker, a question about the manual took about **19 minutes** for the full answer. This is a measurement of that computer, not a prediction for every CPU. For an interactive presentation, a machine with compatible GPU acceleration is preferable; run a test on the instructor's computer before the delivery.

## What is prepared automatically

The package uses **Docker Compose** to start a coordinated set of containers. The instructor runs a single command or script.

1. Build of the frontend, backend, agents and mock backoffice images.
2. Start of the mock backoffice and loading of the Excel dataset included in the repository.
3. Start of Ollama inside Docker.
4. Start of Langfuse and its services; automatic creation of organization, project, account and API keys.
5. Check that the manuals of all eight machines are present.
6. Download of **`llama3.1:8b`**, used by the orchestrator and the agents, and **`nomic-embed-text`**, used for embeddings. Models already present are reused.
7. Real one-token generation test, with the same context window as the chat, before the ingestion starts. In NVIDIA mode, the GPU memory actually used by the model is also checked: if it is zero, the setup stops. In CPU mode the model is unloaded from RAM right away; in GPU mode it stays loaded for up to five minutes of inactivity or until the embedding model is loaded. The weights stay in the volume.
8. PDF text extraction, chunking and construction of the Chroma index.
9. Start of agents, backend and interface, in this order and only after the required steps succeeded.

The chosen model is the 8-billion-parameter Llama 3.1 variant with tool-calling support; the model download is about 4.9 GB. [Official model page](https://ollama.com/library/llama3.1:8b).

The `setup` service ends with **`Exited (0)`** when it is done: this is the expected behaviour. An error during download, ingestion or the generation test prevents the agents and the interface from starting. The scripts also print the last setup messages on error. During testing, with about 8 GB assigned to Docker, the system killed Llama for insufficient memory: seeing the containers running is not enough to know that the chat works.

## First test

After logging in:

1. Open a fleet machine visible to the user.
2. Try a question about the manual, for example: **"Which maintenance checks are planned for this machine?"**
3. Check the cited sources and that the PDF opens.
4. Try an operational question, for example: **"Which recent alarms are recorded for this machine?"**

The operational dataset is synthetic and ends on **4 August 2026**: recent time windows refer to the machine's latest data point.

| Service | Address / access |
|---|---|
| Application | [localhost:8080](http://localhost:8080) |
| API health | [localhost:8080/api/health](http://localhost:8080/api/health) |
| Langfuse | [localhost:3000](http://localhost:3000) |
| Langfuse login | `docente@arol.local` / `ArolDemo2026!` |
| Langfuse project | `AROL Fleet Management` |

After a question, the traces appear in Langfuse with a short delay. Account, project and keys are created through [Langfuse headless initialization](https://langfuse.com/self-hosting/administration/headless-initialization).

This configuration is meant for a **local demo**: it uses declared demo credentials and exposes the app and Langfuse only on `127.0.0.1`. The other services stay inside the Docker network. It is not a configuration for publishing the service on the Internet.

## Stopping and restarting

All the following commands must be run in the extracted folder.

**Stop the project**, keeping models, index, conversations and traces:

```sh
docker compose -f compose.delivery.yml down
```

**Restart:** run `avvia.bat` or `sh avvia.sh` again. The scripts first stop the services that read Chroma, then repeat the checks and wait until the app is ready. Unchanged PDFs and already downloaded models are reused.

When using NVIDIA, always restart with **`avvia-gpu.bat`** or **`sh avvia-gpu.sh`**, also after a source update. The normal scripts select the CPU; models, index and data are the same in both modes. The single-file Compose start commands below also select the CPU; to keep NVIDIA, add `-f compose.delivery.gpu.yml` right after `-f compose.delivery.yml`.

The stack can also be started directly with Compose, while it is stopped:

```sh
docker compose -f compose.delivery.yml up --build --wait --wait-timeout 7200
```

To restart without rebuilding already prepared images, also offline:

```sh
docker compose -f compose.delivery.yml up --wait --wait-timeout 7200 --pull never --no-build
```

This last command requires that the first start already completed successfully and that the required models have not changed.

**Show the status:**

```sh
docker compose -f compose.delivery.yml ps -a
```

**Follow the preparation** from a second terminal, once the `setup` container has been created:

```sh
docker compose -f compose.delivery.yml logs -f setup
```

**Show the application logs:**

```sh
docker compose -f compose.delivery.yml logs --tail 100 backend agents
```

## Manuals and persistence

The original PDFs are in `data/manuals/` and are mounted read-only. Do not move or delete the extracted folder while the project is in use.

Docker volumes keep Ollama models, Chroma index, application database, loaded dataset and Langfuse data separately. They are isolated from the development environment by the `arol-delivery` project name. A normal `down` does not delete them.

The ingestion records a PDF as complete only after all its chunks are saved. If it is interrupted, the next start resumes the incomplete manuals; unchanged ones are skipped. A changed PDF is reindexed; changing the embedding model rebuilds the index.

To update the manuals, stop the stack, replace the PDFs keeping the expected names and restart with the script. The package requires at least one manual for each of the eight machines.

**Full reset, only to delete all the demo data:**

```sh
docker compose -f compose.delivery.yml down --volumes
```

This also deletes the downloaded models, the conversations and the traces. The next start will have to repeat download and ingestion. The PDFs in the folder are kept.

## Optional NVIDIA GPU

**Llama 3.1 8B can use an NVIDIA GPU through Ollama.** The package keeps the same Ollama image and the same models; `compose.delivery.gpu.yml` assigns the GPUs to the Ollama service only. The image pinned to version 0.13.5 already includes the CUDA libraries: there is no need to install Python, PyTorch or the CUDA Toolkit inside the other containers. [Official Dockerfile of the included version](https://github.com/ollama/ollama/blob/v0.13.5/Dockerfile).

### Computer preparation (once)

- **Windows 10/11 with NVIDIA:** install up-to-date NVIDIA drivers, update WSL with `wsl --update` and enable **Use the WSL 2 based engine** in Docker Desktop. Use Linux containers. The Hyper-V backend does not provide this GPU passthrough to containers. [Official Docker prerequisites for Windows](https://docs.docker.com/desktop/features/gpu/).
- **Linux with NVIDIA:** use Docker Engine on the system with the GPU, install the drivers and the **NVIDIA Container Toolkit** following the [official NVIDIA guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Configure the runtime and restart Docker with the following commands. The NVIDIA guide also covers the specific configuration for rootless Docker.

```sh
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Restarting Docker also affects any other container running on the computer. Drivers and runtime are prerequisites of the host system and must be configured once by whoever administers the PC. [Ollama procedure for NVIDIA in Docker](https://docs.ollama.com/docker).

This mode is meant for PCs/servers with an Ollama-compatible NVIDIA GPU and up-to-date drivers. It does not enable Metal on Macs nor AMD GPUs. Jetson/JetPack systems need a specific configuration and are not covered by the standard launcher.

As an estimate for quantized Llama 8B with an 8,192-token context, plan for **8 GB of free VRAM as a starting point**, preferably **12 GB for some headroom**. This is not a certified minimum: the memory needed depends on GPU, context and model. VRAM is separate from system RAM; the resources required by the other services still apply. With little VRAM, Ollama can split the model between GPU and CPU, reducing the speed benefit.

### Simple start and automatic checks

- **Windows:** double-click **`avvia-gpu.bat`**.
- **Linux:** run **`sh avvia-gpu.sh`** in the extracted folder.

The same starts are available as `avvia.bat --gpu` and `sh avvia.sh --gpu`. Always use the GPU launcher for later restarts; to go back to the CPU, use the normal one.

The launcher first runs `nvidia-smi -L` in a temporary container built from the same Ollama image, with the same GPU request. If Docker does not see NVIDIA, it stops **before stopping the application already running**. During the setup, after a real test generation, it checks `size_vram` in the [Ollama loaded models API](https://docs.ollama.com/api/ps):

- **`GPU check passed`** means Llama allocated GPU memory.
- **`partially on GPU`** reports mixed GPU/CPU usage: the start is allowed, but it can be slower.
- **`no GPU memory`** blocks the setup; the package does not declare GPU mode ready if Llama is running on the CPU only.

GPU usage is checked for Llama during the setup. The embedding model uses the same Ollama server, which manages its execution automatically; its loading on the GPU is not certified separately.

For a manual check of NVIDIA access, without starting the app:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml run --rm --no-deps --entrypoint nvidia-smi ollama -L
```

To start directly through Compose, while the stack is stopped:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml up --build --wait --wait-timeout 7200
```

During a chat question, or right after it, check where the model is loaded:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml exec ollama ollama ps
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml logs --tail 100 setup ollama
```

The `PROCESSOR` column of `ollama ps` distinguishes GPU, CPU and mixed loading. If it shows no models, the keep-alive period may have expired: repeat during a request. The embedding model can temporarily replace Llama because the package loads one model at a time.

To reduce the memory needed, `DELIVERY_NUM_CTX=4096` can be set before the GPU launcher: `export DELIVERY_NUM_CTX=4096` on Linux, `set DELIVERY_NUM_CTX=4096` in the Windows Command Prompt or `$env:DELIVERY_NUM_CTX="4096"` in PowerShell. A smaller context leaves less room for history and documents; it does not guarantee equivalent performance or quality.

NVIDIA acceleration can improve inference times, but it does not fix the model's reasoning, translation or tool-choice errors. The configuration follows the [Docker Compose GPU specification](https://docs.docker.com/compose/how-tos/gpu-support/); a test on a real GPU is still needed to measure memory and timing.

## Troubleshooting

| Problem | Solution |
|---|---|
| Docker does not respond | Open Docker Desktop and wait until the engine is ready. On Linux, start Docker Engine. |
| Port already in use | Stop the other application or the development stack using 8080/3000. |
| `setup` ends with an error | Read `docker compose -f compose.delivery.yml logs setup`. Fix the cause and run the script again. |
| `Missing manuals`, `No PDF manuals` or folder not found | Check that the ZIP was fully extracted and contains all the PDFs in `data/manuals/`. |
| Invalid PDF name or unknown serial | Restore the original name `<serial>_manual_EN.pdf`. |
| Download interrupted | Restore the connection and run the script again. Data already downloaded stays in the Ollama volume. |
| Preparation seems stuck | Follow the `setup` logs; indexing can take long on CPU. |
| Container exited with code 137, memory error or very slow chat | Increase the memory available to Docker and close heavy applications; use the GPU variant if available. |
| App running but answers very slow | On CPU, several minutes per question are possible. Check the `backend`, `agents` and `ollama` logs. |
| `could not select device driver` or `nvidia-smi` fails | Check drivers and NVIDIA Container Toolkit on Linux, or drivers, WSL2 and the Docker Desktop backend on Windows. The GPU launcher does not fall back to the CPU automatically. |
| `no GPU memory` during the setup | Read the Ollama logs: check GPU compatibility, drivers, runtime and free VRAM. Run the GPU launcher again after the fix. |
| `partially on GPU` or mixed usage in `ollama ps` | Free VRAM used by other applications or try `DELIVERY_NUM_CTX=4096`; the part of the model on the CPU can slow down answers. |
| Incomplete answer or badly chosen tools | Llama 3.1 8B is a compact local model; answers must be checked against the sources and their correctness is not guaranteed. |
| Old interface still in the browser | Reload the page; if needed, clear the site/PWA data for `localhost:8080`. |

For advanced diagnosis, check the installed models:

```sh
docker compose -f compose.delivery.yml exec ollama ollama list
```

The optional settings `DELIVERY_LLM_MODEL`, `DELIVERY_EMBEDDING_MODEL`, `DELIVERY_NUM_CTX`, `DELIVERY_APP_PORT` and `DELIVERY_LANGFUSE_PORT` can be defined in the terminal environment before the start. The defaults need no configuration. An alternative chat model must support tool calling and fit in the available memory.

## Package preparation — for the project team

This section requires no action from the instructor.

The AROL manuals are not versioned in Git. Before the delivery they must be included in the ZIP reserved for the course:

```text
data/manuals/
  15610_manual_EN.pdf
  17203_manual_EN.pdf
  17478_manual_EN.pdf
  17579_manual_EN.pdf
  A2055_manual_EN.pdf
  A2064_manual_EN.pdf
  A2132_manual_EN.pdf
  A4344_manual_EN.pdf
```

From the full working copy of the repository, build the package with:

```sh
python3 scripts/package_delivery.py
```

The result is **`dist-delivery/arol-fleet-management.zip`**: it contains the current sources, the Excel dataset, the scripts, this guide and the eight PDFs. It excludes personal `.env` files, databases, local indexes, Python environments and `node_modules`. The package must be rebuilt after the last source changes.

Deliver this ZIP through the course's private channel. The manuals are AROL material and must not be added to the public repository. The package does not contain the Docker images or the model weights: they are downloaded on the first start.

Before the final delivery, test the ZIP on a machine with adequate resources, checking login, an answer with sources from the manual, a question on operational data and a trace in Langfuse. The quality of Llama 3.1 8B answers must be checked on the computer used for the demo.

### Package test (25 October 2026)

Tested environment: macOS ARM64, 32 GB of physical RAM, Docker configured with 16 GB, CPU inference.

- Start through `sh avvia.sh` completed; all application services are ready.
- Real download of both models and ingestion of **8 manuals / 2,155 chunks** completed. They are reused on restart.
- Initial generation check, login, machine list and opening the PDF from the browser verified.
- Real orchestrator trace present in the automatically created Langfuse project.
- **39 selected tests passed**: 29 for agents/ingestion/bootstrap, 5 for backend and 5 for mock backoffice. The existing tests in `agents/tests/test_agent_failures.py` have errors and are not among these 39: the whole suite is not claimed to pass.
- ZIP extracted and images rebuilt successfully from the extracted copy: it contains the eight PDFs and the updated sources, without personal `.env` files.
- Full chat on the manual verified through the frontend: answer in Italian and five citations to PDF pages **95, 129 and 133**, in **1,136.8 seconds (about 19 minutes)**. The PDF was also opened in the browser at page 95.
- Real access to operational data verified through the agent client: for `MCH-0001`, in the 29 July–4 August 2026 window, there are 14 alarms. The second chat test on alarms was interrupted after it started; its final answer with Llama is not claimed as verified.

**Limits found in the model test:** for a simple greeting, Llama 3.1 8B took about 7 minutes for the first decision and wrongly called `search_iot` with an empty question. This test was interrupted. The answer on the manual arrived with relevant sources, but with translation and formatting defects. A successful installation and the automated tests do not certify the quality of the model's answers: this 8B version needs a content check before the demo.

The Windows script and the NVIDIA variant are ready; they were not run on Windows/NVIDIA hardware during this test.

### NVIDIA start checks (26 October 2026)

- Added `avvia-gpu.bat` and `avvia-gpu.sh`, with an NVIDIA check before stopping the app and a check of Llama's VRAM before the ingestion.
- CPU and NVIDIA Compose configurations validated, including the GPU request, the setup variables and the reuse of the same volumes.
- Agents image rebuilt; **36 targeted agent tests** and **5 POSIX launcher tests** passed. The positive GPU cases are simulated: they cover fully/partially VRAM-loaded models, CPU fallback, missing model and failed check.
- On the Mac without NVIDIA the GPU launcher was actually run: it refused to start and the app containers already running kept running.
- Real one-token test on CPU completed with the new bootstrap. Then, requesting the GPU from the same Ollama, the check correctly rejected zero VRAM.

It was not possible to run a generation on a real NVIDIA GPU or to run the `.bat` files on Windows. Response times, required VRAM and behaviour on a specific GPU model are therefore not certified. The 25 October tests remain the reference for the full chat path on CPU.
