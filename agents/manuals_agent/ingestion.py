"""Index manuals with per-file completion records, safe to retry after failure."""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf

from core.config import settings
from core.docs_client import get_docs_client
from core.vectorstore import get_vector_store, reset_vector_store

MANUALS_DIR = Path(settings.MANUALS_PATH)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
FILENAME_PATTERN = re.compile(r"^(?P<serial>.+)_manual_(?P<language>[A-Za-z]{2})$")


@dataclass(frozen=True)
class Manual:
    path: Path
    machine_id: str
    serial: str
    language: str


def parse_filename(pdf_path: Path) -> tuple[str, str] | None:
    match = FILENAME_PATTERN.match(pdf_path.stem)
    return (match["serial"], match["language"].upper()) if match else None


def load_serial_to_machine_id() -> dict[str, str]:
    machines = asyncio.run(get_docs_client().list_machines())
    return {m["serial_number"]: m["machine_id"] for m in machines}


def prepare_manuals(*, require_all: bool = False) -> list[Manual]:
    """Validate inputs before downloading models or modifying the index."""
    pdfs = sorted(MANUALS_DIR.glob("*.pdf"))
    if not pdfs:
        raise ValueError(f"No PDF manuals in {MANUALS_DIR}. Copy the course PDFs into data/manuals.")
    registry = load_serial_to_machine_id()
    manuals = []
    for path in pdfs:
        parsed = parse_filename(path)
        if parsed is None:
            raise ValueError(f"Invalid filename {path.name}: expected <serialNumber>_manual_<LANG>.pdf")
        serial, language = parsed
        if serial not in registry:
            raise ValueError(f"Unknown serial {serial} in {path.name}; not in the fleet registry")
        manuals.append(Manual(path, registry[serial], serial, language))
    missing = set(registry) - {manual.serial for manual in manuals}
    if require_all and missing:
        raise ValueError(f"Missing manuals for serials: {', '.join(sorted(missing))}")
    return manuals


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    with fitz.open(pdf_path) as doc:
        return [(page_num + 1, page.get_text()) for page_num, page in enumerate(doc)]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    return [chunk for start in range(0, len(text), size - overlap)
            if (chunk := text[start:start + size].strip())]


def ingest_pdf(pdf_path: Path, machine_id: str, language: str, serial: str) -> int:
    store = get_vector_store()
    ids, chunks, metadatas = [], [], []
    # Include the filename so translations of the same manual never collide.
    doc_id = hashlib.sha256(pdf_path.name.encode()).hexdigest()[:24]
    for page_num, page_text in extract_pages(pdf_path):
        for i, chunk in enumerate(chunk_text(page_text)):
            ids.append(f"{machine_id}_{doc_id}_p{page_num}_c{i}")
            chunks.append(chunk)
            metadatas.append({
                "machine_id": machine_id, "serial_number": serial,
                "doc": pdf_path.name, "page": page_num, "language": language,
            })
    if not chunks:
        raise ValueError(f"No extractable text in {pdf_path.name}; an OCR version is required")
    store.add(ids=ids, chunks=chunks, metadatas=metadatas)
    return len(chunks)


def _save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(path)


def seed_manuals(manuals: list[Manual] | None = None) -> None:
    manuals = prepare_manuals() if manuals is None else manuals
    manifest_path = Path(settings.CHROMA_PATH) / "ingestion-manifest.json"
    signature = {
        "version": 2, "embedding_model": settings.EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP,
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    if manifest.get("signature") != signature:
        print("Initializing index (new index, embedding model or chunk format)", flush=True)
        store = reset_vector_store()
        manifest = {"signature": signature, "documents": {}}
        _save_manifest(manifest_path, manifest)
    else:
        store = get_vector_store()

    documents = manifest["documents"]
    for name in set(documents) - {manual.path.name for manual in manuals}:
        store.delete_document(name)
        del documents[name]
        _save_manifest(manifest_path, manifest)

    for manual in manuals:
        with manual.path.open("rb") as pdf:
            fingerprint = {
                "sha256": hashlib.file_digest(pdf, "sha256").hexdigest(),
                "machine_id": manual.machine_id, "language": manual.language,
            }
        previous = documents.get(manual.path.name, {})
        if (all(previous.get(key) == value for key, value in fingerprint.items())
                and previous.get("chunks", 0) > 0
                and store.count_document(manual.path.name) == previous["chunks"]):
            print(f"Already ingested {manual.path.name}", flush=True)
            continue

        # Completion is recorded only AFTER every embedding batch succeeds.
        # Clear partial or outdated chunks before retrying the complete PDF.
        # Track pending files too, so removing a PDF after an interrupted run
        # also removes any partial chunks on the next run.
        documents[manual.path.name] = {"pending": True}
        _save_manifest(manifest_path, manifest)
        store.delete_document(manual.path.name)
        print(f"Indexing {manual.path.name}...", flush=True)
        count = ingest_pdf(manual.path, manual.machine_id, manual.language, manual.serial)
        documents[manual.path.name] = {**fingerprint, "chunks": count}
        _save_manifest(manifest_path, manifest)
        print(f"Ingested {manual.path.name} -> {manual.machine_id}: {count} chunks", flush=True)
    print(f"Manuals ready: {len(documents)} PDFs", flush=True)


if __name__ == "__main__":
    seed_manuals()
