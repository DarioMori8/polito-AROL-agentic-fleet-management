"""One-shot Docker setup: check manuals, download models, build the RAG index."""

import sys

import ollama

from core.config import settings
from manuals_agent.ingestion import prepare_manuals, seed_manuals


def ensure_model(client, model: str, *, require_tools: bool = False) -> None:
    try:
        details = client.show(model)
        print(f"Model already available: {model}", flush=True)
    except ollama.ResponseError as exc:
        if exc.status_code != 404:
            raise
        print(f"Downloading {model} (first start only)...", flush=True)
        last_progress = None
        for event in client.pull(model, stream=True):
            total = event.get("total") or 0
            completed = event.get("completed") or 0
            percent = (completed * 100 // total // 10) * 10 if total else None
            progress = (event.get("status"), event.get("digest"), percent)
            if progress != last_progress:
                suffix = f" {percent}%" if percent is not None else ""
                print(f"{model}: {event.get('status', '')}{suffix}", flush=True)
                last_progress = progress
        details = client.show(model)
    if require_tools and "tools" not in (details.get("capabilities") or []):
        raise ValueError(f"Model {model} does not support tool calling. Use llama3.1:8b.")


def verify_inference(client) -> None:
    """Exercise the configured context size before announcing a usable app."""
    print("Checking that the chat model can run with the available memory...", flush=True)
    try:
        response = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{"role": "user", "content": "Reply OK."}],
            options={"num_ctx": settings.OLLAMA_NUM_CTX, "num_predict": 1},
            keep_alive=0,
        )
    except ollama.ResponseError as exc:
        if any(word in str(exc).lower() for word in ("memory", "killed", "allocate")):
            raise RuntimeError(
                "Ollama could not load the chat model with the available memory. "
                "Assign at least 16 GB of RAM to Docker Desktop, apply/restart Docker, "
                "then run the startup script again. Models and indexed manuals are preserved. "
                f"Original error: {exc}"
            ) from exc
        raise
    if not response.get("done"):
        raise RuntimeError("Ollama did not complete the startup inference check")
    print("Chat model inference check passed", flush=True)


def main() -> None:
    manuals = prepare_manuals(require_all=True)
    print(f"Validated {len(manuals)} manuals against the fleet registry", flush=True)
    client = ollama.Client(host=settings.OLLAMA_BASE_URL, timeout=1800)
    ensure_model(client, settings.OLLAMA_MODEL, require_tools=True)
    ensure_model(client, settings.EMBEDDING_MODEL)
    seed_manuals(manuals)
    verify_inference(client)
    print("Setup complete: models and manuals are ready.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SETUP FAILED: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
