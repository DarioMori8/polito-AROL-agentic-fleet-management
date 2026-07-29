from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SearchManualTask(BaseModel):
    """Request payload sent to the Manuals Agent's /agents/manuals/search endpoint."""
    query: str
    machine_id: str


class Citation(BaseModel):
    """A single source reference backing an agent's answer."""
    doc: str
    page: int
    snippet: str


class SearchManualResponse(BaseModel):
    """Response returned by the Manuals Agent."""
    answer: str
    citations: list[Citation] = []
    confidence: float

class SearchDocsTask(BaseModel):
    """Request payload sent to the Docs Agent's /agents/docs/search endpoint."""
    query: str
    machine_id: str


class Document(BaseModel):
    document_id: str
    order_id: str
    quote_id: str | None = None
    machine_id: str
    type: str
    title: str
    content: str
    upload_date: str


class Item(BaseModel):
    sku: str
    description: str
    quantity: int


class Order(BaseModel):
    order_id: str
    quote_id: str | None = None
    customer_name: str
    machine_id: str
    machine_model: str
    order_type: str
    status: str
    order_date: str
    estimated_delivery_date: str
    actual_delivery_date: str | None = None
    amount_eur: float
    items: list[Item] = []


class Revision(BaseModel):
    revision_number: int
    date: str
    amount_eur: float
    notes: str


class Quote(BaseModel):
    quote_id: str
    customer_name: str
    machine_id: str
    machine_model: str
    date_created: str
    status: str
    valid_until: str
    current_amount_eur: float
    linked_order_id: str | None = None
    revisions: list[Revision] = []


# The Docs Agent can back its answer with heterogeneous records, so each source
# variant carries a `kind` tag: it survives into the response and lets the
# frontend pick the right way to render it.
class DocumentSource(Document):
    kind: Literal["document"] = "document"


class OrderSource(Order):
    kind: Literal["order"] = "order"


class QuoteSource(Quote):
    kind: Literal["quote"] = "quote"


Source = Annotated[
    DocumentSource | OrderSource | QuoteSource,
    Field(discriminator="kind"),
]


class SearchDocsResponse(BaseModel):
    """Response returned by the Docs Agent."""
    answer: str
    sources: list[Source] = []
    confidence: float