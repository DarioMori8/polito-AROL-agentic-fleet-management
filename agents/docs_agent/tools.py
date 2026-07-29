SEARCH_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the contractual documents attached to the machine: contracts, technical "
            "attachments, delivery notes and invoices. Use this for questions about clauses, "
            "warranty terms, payment conditions, technical configuration or delivery details. "
            "Returns the matching documents with their full text content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A focused search query describing what to look for in the documents, "
                        "e.g. 'warranty duration' or 'payment terms'"
                    ),
                },
                "document_type": {
                    "type": "string",
                    "enum": ["contract", "attachment", "delivery_note", "invoice"],
                    "description": (
                        "Restrict the search to one kind of document, only when the user "
                        "explicitly asked for it (e.g. 'the invoice', 'the contract')"
                    ),
                },
                "order_id": {
                    "type": "string",
                    "description": (
                        "Restrict the search to documents linked to a specific order, only when "
                        "the user mentioned an order number, e.g. 'ORD-2026-001'"
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

SEARCH_ORDERS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_orders",
        "description": (
            "Look up the orders placed for the machine, either the machine itself or spare "
            "parts. Use this for questions about order status, delivery dates, amounts or "
            "which parts were ordered. Call it without filters to list every order. "
            "This tool does NOT do free-text search: extract the exact filters from the "
            "user's question instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": (
                        "Exact order id, only when the user mentioned one, e.g. 'ORD-2026-001'"
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "confirmed",
                        "in_production",
                        "shipped",
                        "delivered",
                        "cancelled",
                    ],
                    "description": (
                        "Filter by order status, only when the user asked about a specific one "
                        "(e.g. 'what has already been shipped?')"
                    ),
                },
                "order_type": {
                    "type": "string",
                    "enum": ["machine", "spare_parts"],
                    "description": (
                        "Filter by what was ordered: the machine itself, or spare parts. Only "
                        "when the user's question is clearly about one of the two"
                    ),
                },
            },
            "required": [],
        },
    },
}

SEARCH_QUOTES_TOOL = {
    "type": "function",
    "function": {
        "name": "search_quotes",
        "description": (
            "Look up the commercial quotes (price offers) issued for the machine, including "
            "the full revision history of each negotiation. Use this for questions about "
            "offered prices, quote validity, why a price changed, or whether a quote turned "
            "into an order. Quotes come BEFORE orders: if the user asks about something "
            "already purchased, use search_orders instead. Call it without filters to list "
            "every quote."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quote_id": {
                    "type": "string",
                    "description": (
                        "Exact quote id, only when the user mentioned one, e.g. 'Q-2026-001'"
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "sent", "revised", "accepted", "rejected"],
                    "description": (
                        "Filter by quote status, only when the user asked about a specific one "
                        "(e.g. 'which offers are still open?')"
                    ),
                },
            },
            "required": [],
        },
    },
}

TOOLS = [SEARCH_DOCUMENTS_TOOL, SEARCH_ORDERS_TOOL, SEARCH_QUOTES_TOOL]
