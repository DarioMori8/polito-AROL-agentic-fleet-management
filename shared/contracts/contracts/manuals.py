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
    """Request payload sent to the Docs Agent's /agents/docs/search endpoint.

    Commercial records hang off the customer, not off the machine: an order and a
    quote carry a companyId, and reach a machine only through the lines of a quote
    revision — when they reach one at all, since a quote for a machine that is not
    installed yet has no machine to point to.

    So `company_id` is the boundary and is always required: it is the tenant
    limit, resolved by the backend from the scanned machine and never chosen by
    the model. `machine_id` is context, and only narrows within that boundary.
    """
    query: str
    company_id: str
    machine_id: str | None = None


# The models below mirror the Q2 dataset. Two things there are not where an
# intuition built on invoices would put them: an order carries no machine and no
# amount of its own — both come from the lines of the approved revision of its
# quote — and a quote carries no status, because the status lives on its latest
# revision.


class OrderLine(BaseModel):
    """A line of the approved revision, i.e. what the order actually covers."""
    description: str
    price: float
    machine_id: str | None = None


class Order(BaseModel):
    order_id: str
    quote_id: str
    customer_name: str
    status: str
    shipment_status: str
    order_date: str
    expected_delivery_date: str
    currency: str
    total_amount: float
    notes: str | None = None
    lines: list[OrderLine] = []
    # OrderLines only tracks fulfilment, with no item or amount of its own, so it
    # is summarised as a count per state rather than listed line by line.
    fulfillment: dict[str, int] = {}


class QuoteRevision(BaseModel):
    revision_number: int
    status: str
    issued_at: str
    discount_rate: float
    amount: float | None = None
    change_summary: str | None = None


class Quote(BaseModel):
    quote_id: str
    customer_name: str
    created_at: str
    valid_until: str
    currency: str
    description: str | None = None
    current_status: str
    current_amount: float | None = None
    linked_order_id: str | None = None
    revisions: list[QuoteRevision] = []


# The Docs Agent can back its answer with heterogeneous records, so each source
# variant carries a `kind` tag: it survives into the response and lets the
# frontend pick the right way to render it.
class OrderSource(Order):
    kind: Literal["order"] = "order"


class QuoteSource(Quote):
    kind: Literal["quote"] = "quote"


Source = Annotated[
    OrderSource | QuoteSource,
    Field(discriminator="kind"),
]


class SearchDocsResponse(BaseModel):
    """Response returned by the Docs Agent."""
    answer: str
    sources: list[Source] = []
    confidence: float