import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(title="AROL Mock Backoffice (stand-in for ERP/CRM/Document Store)")

documents: list[dict] = json.loads((DATA_DIR / "documents.json").read_text())
orders: list[dict] = json.loads((DATA_DIR / "orders.json").read_text())
quotes: list[dict] = json.loads((DATA_DIR / "quotes.json").read_text())


@app.get("/health")
async def health():
    return {"status": "ok"}


class DocumentSearchRequest(BaseModel):
    query: str
    machine_id: str
    document_type: str | None = None
    order_id: str | None = None


@app.post("/documents/search")
async def search_documents(req: DocumentSearchRequest):
    # machine_id is the access-control boundary: required on every endpoint and
    # always applied first, so no filter combination can widen the result set
    # beyond the caller's machine.
    results = [d for d in documents if d["machine_id"] == req.machine_id]

    if req.document_type:
        results = [d for d in results if d["type"] == req.document_type]

    if req.order_id:
        results = [d for d in results if d["order_id"] == req.order_id]

    if req.query:
        results = _rank_by_query(results, req.query)

    return {"results": results}


# Words carried by any natural-language query; matching on them would rank every
# document equally and drown the meaningful terms.
STOPWORDS = {
    "a", "an", "and", "any", "are", "about", "for", "from", "how", "in", "is", "it",
    "long", "many", "me", "much", "my", "of", "on", "or", "our", "show", "tell",
    "that", "the", "there", "to", "was", "what", "when", "which", "who", "with",
}


def _rank_by_query(candidates: list[dict], query: str) -> list[dict]:
    """Keep documents matching at least one query term, best match first.

    An LLM asks in natural language ("how long is the warranty?"), so matching the
    query as one literal string finds nothing. Scoring per term keeps multi-word
    questions working without pulling in a full search engine.
    """
    terms = {t for t in _tokenize(query) if t not in STOPWORDS}
    if not terms:
        return candidates

    scored = []
    for doc in candidates:
        haystack = _tokenize(f"{doc['title']} {doc['content']}")
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, doc))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored]


def _tokenize(text: str) -> set[str]:
    return {word.strip(".,;:()'\"") for word in text.lower().split()}


@app.get("/orders")
async def search_orders(
    machine_id: str,
    order_id: str | None = None,
    status: str | None = None,
    order_type: str | None = None,
):
    results = [o for o in orders if o["machine_id"] == machine_id]

    if order_id:
        results = [o for o in results if o["order_id"] == order_id]

    if status:
        results = [o for o in results if o["status"] == status]

    if order_type:
        results = [o for o in results if o["order_type"] == order_type]

    return {"results": results}


@app.get("/quotes")
async def search_quotes(
    machine_id: str,
    quote_id: str | None = None,
    status: str | None = None,
):
    results = [q for q in quotes if q["machine_id"] == machine_id]

    if quote_id:
        results = [q for q in results if q["quote_id"] == quote_id]

    if status:
        results = [q for q in results if q["status"] == status]

    return {"results": results}
