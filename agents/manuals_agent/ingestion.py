import asyncio
import re
from pathlib import Path

import fitz  # pymupdf

from core.config import settings
from core.docs_client import get_docs_client
from core.vectorstore import get_vector_store

MANUALS_DIR = Path(settings.MANUALS_PATH)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Dataset convention: manuals are named <serialNumber>_manual_<LANG>.pdf, and are
# machine-specific rather than model-specific — two machines of the same model
# have different, non-interchangeable manuals.
FILENAME_PATTERN = re.compile(r"^(?P<serial>.+)_manual_(?P<language>[A-Za-z]{2})$")


def parse_filename(pdf_path: Path) -> tuple[str, str] | None:
    match = FILENAME_PATTERN.match(pdf_path.stem)
    if match is None:
        return None
    return match["serial"], match["language"].upper()


def load_serial_to_machine_id() -> dict[str, str]:
    """Map each serial number to the machineId the rest of the platform uses.

    The file name gives a serial, but everything else — the QR code, the backend,
    the chat request, the other agents — speaks machineId. Indexing the chunks
    under the serial would leave one identifier out of step with all the others,
    so the mapping is resolved once here, at ingestion time, and never again at
    query time. It only exists in the fleet registry, hence the call to the
    backoffice: 8 rows, and it is already a dependency of this service.
    """
    machines = asyncio.run(get_docs_client().list_machines())
    return {m["serial_number"]: m["machine_id"] for m in machines}


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    doc = fitz.open(pdf_path)
    return [(page_num + 1, page.get_text()) for page_num, page in enumerate(doc)]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def ingest_pdf(pdf_path: Path, machine_id: str, language: str, serial: str) -> int:
    store = get_vector_store()
    ids, chunks, metadatas = [], [], []

    for page_num, page_text in extract_pages(pdf_path):
        for i, chunk in enumerate(chunk_text(page_text)):
            ids.append(f"{machine_id}_p{page_num}_c{i}")
            chunks.append(chunk)
            metadatas.append(
                {
                    "machine_id": machine_id,
                    "serial_number": serial,
                    "doc": pdf_path.name,
                    "page": page_num,
                    "language": language,
                }
            )

    if chunks:
        store.add(ids=ids, chunks=chunks, metadatas=metadatas)
    return len(chunks)


def seed_manuals() -> None:
    store = get_vector_store()

    pdfs = sorted(MANUALS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No pdf found in {MANUALS_DIR}")
        return

    serial_to_machine_id = load_serial_to_machine_id()

    for pdf_path in pdfs:
        parsed = parse_filename(pdf_path)
        if parsed is None:
            print(f"Skipped {pdf_path.name}: expected <serialNumber>_manual_<LANG>.pdf")
            continue

        serial, language = parsed
        machine_id = serial_to_machine_id.get(serial)
        if machine_id is None:
            # Better to skip loudly than to index under the serial: a chunk whose
            # machine_id nobody ever asks for is invisible, and invisible in a RAG
            # system looks exactly like an answer that isn't in the manual.
            print(f"Skipped {pdf_path.name}: serial {serial} is not in the fleet registry")
            continue

        # Checked per manual rather than on the collection as a whole: dropping a
        # new PDF in the volume ingests only that one, and an interrupted run
        # resumes from where it stopped instead of being skipped entirely.
        if store.has_chunks({"machine_id": machine_id}):
            print(f"Already ingested {pdf_path.name}")
            continue

        n = ingest_pdf(pdf_path, machine_id, language, serial)
        print(f"Ingested {pdf_path.name} -> {machine_id}: {n} chunk")


if __name__ == "__main__":
    seed_manuals()
