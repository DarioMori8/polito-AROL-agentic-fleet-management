from pathlib import Path

import fitz  # pymupdf

from core.vectorstore import get_vector_store

SAMPLES_DIR = Path(__file__).parent / "samples_manual"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DEFAULT_MACHINE_ID = "generic"


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


def ingest_pdf(pdf_path: Path, machine_id: str = DEFAULT_MACHINE_ID) -> int:
    store = get_vector_store()
    ids, chunks, metadatas = [], [], []

    for page_num, page_text in extract_pages(pdf_path):
        for i, chunk in enumerate(chunk_text(page_text)):
            ids.append(f"{pdf_path.stem}_p{page_num}_c{i}")
            chunks.append(chunk)
            metadatas.append({"doc": pdf_path.name, "page": page_num, "machine_id": machine_id})

    if chunks:
        store.add(ids=ids, chunks=chunks, metadatas=metadatas)
    return len(chunks)


def seed_if_empty() -> None:
    store = get_vector_store()
    existing = store.collection.count()
    if existing > 0:
        print(f"Already seeded collection.")
        return

    pdfs = sorted(SAMPLES_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No pdf found in {SAMPLES_DIR}")
        return

    for pdf_path in pdfs:
        n = ingest_pdf(pdf_path)
        print(f"Ingested {pdf_path.name}: {n} chunk")


if __name__ == "__main__":
    seed_if_empty()
