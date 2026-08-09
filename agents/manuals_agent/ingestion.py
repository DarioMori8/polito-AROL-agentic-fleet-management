import re
from pathlib import Path

import fitz  # pymupdf

from core.config import settings
from core.vectorstore import get_vector_store

MANUALS_DIR = Path(settings.MANUALS_PATH)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Dataset convention: manuals are named <serialNumber>_manual_<LANG>.pdf and are
# machine-specific, not model-specific. The serial number in the file name is the
# join key between a machine and its manual, so it is what gets stored as the
# machine_id of a manual's chunks — the identifier the whole platform speaks.
FILENAME_PATTERN = re.compile(r"^(?P<machine_id>.+)_manual_(?P<language>[A-Za-z]{2})$")


def parse_filename(pdf_path: Path) -> tuple[str, str] | None:
    match = FILENAME_PATTERN.match(pdf_path.stem)
    if match is None:
        return None
    return match["machine_id"], match["language"].upper()


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


def ingest_pdf(pdf_path: Path, machine_id: str, language: str) -> int:
    store = get_vector_store()
    ids, chunks, metadatas = [], [], []

    for page_num, page_text in extract_pages(pdf_path):
        for i, chunk in enumerate(chunk_text(page_text)):
            ids.append(f"{machine_id}_p{page_num}_c{i}")
            chunks.append(chunk)
            metadatas.append(
                {
                    "machine_id": machine_id,
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

    for pdf_path in pdfs:
        parsed = parse_filename(pdf_path)
        if parsed is None:
            print(f"Skipped {pdf_path.name}: expected <serialNumber>_manual_<LANG>.pdf")
            continue

        machine_id, language = parsed
        # Checked per manual rather than on the collection as a whole: dropping a
        # new PDF in the volume ingests only that one, and an interrupted run
        # resumes from where it stopped instead of being skipped entirely.
        if store.has_chunks({"machine_id": machine_id}):
            print(f"Already ingested {pdf_path.name}")
            continue

        n = ingest_pdf(pdf_path, machine_id, language)
        print(f"Ingested {pdf_path.name} (machine_id {machine_id}): {n} chunk")


if __name__ == "__main__":
    seed_manuals()
