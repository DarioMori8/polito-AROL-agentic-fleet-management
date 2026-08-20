from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SearchDocsTask(BaseModel):
    """Request payload sent to the Docs Agent's /agents/docs/search endpoint.

    Commercial records hang off the customer, not off the machine: an order and
    a quote carry a companyId, and reach a machine only through quote revision
    lines. Therefore `company_id` is the tenant boundary; `machine_id` can only
    narrow the search within that company.
    """

    query: str
    company_id: str
    machine_id: str | None = None


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
    lines: list[OrderLine] = Field(default_factory=list)
    # OrderLines only tracks fulfilment, with no item or amount of its own.
    fulfillment: dict[str, int] = Field(default_factory=dict)


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
    revisions: list[QuoteRevision] = Field(default_factory=list)


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
    sources: list[Source] = Field(default_factory=list)
    confidence: float
