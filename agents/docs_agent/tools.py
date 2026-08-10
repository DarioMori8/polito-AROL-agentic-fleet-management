SEARCH_ORDERS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_orders",
        "description": (
            "Look up the confirmed orders that cover this machine. Use it for questions "
            "about what was purchased, order status, shipment or delivery dates, and how "
            "much an order was worth. Each order comes back with the lines of the approved "
            "quote revision it was generated from, so the itemised content and the total "
            "are already in the result. Call it without filters to list every order. "
            "This tool does NOT do free-text search: extract the exact filters from the "
            "user's question instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "this_machine_only": {
                    "type": "boolean",
                    "description": (
                        "Set to true to restrict the search to records that concern the "
                        "machine the operator scanned. Leave it out for questions about the "
                        "customer's commercial relationship in general — a quote for a "
                        "machine that has not been installed yet belongs to the customer "
                        "and to no machine, so it is only found with this off."
                    ),
                },
                "order_id": {
                    "type": "string",
                    "description": (
                        "Exact order id, only when the user mentioned one, e.g. 'ORD-2025-0001'"
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["Confirmed", "In production", "Delivered", "Closed"],
                    "description": (
                        "Filter by order status, only when the user asked about a specific one "
                        "(e.g. 'what is still in production?')"
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
            "Look up the commercial quotes issued for this machine, each with its full "
            "revision history: number, status, date, discount, amount and a summary of what "
            "changed. Use it for questions about offered prices, quote validity, why a price "
            "changed during a negotiation, or whether a quote became an order. Quotes come "
            "BEFORE orders: if the user asks about something already purchased, use "
            "search_orders instead. Call it without filters to list every quote."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "this_machine_only": {
                    "type": "boolean",
                    "description": (
                        "Set to true to restrict the search to records that concern the "
                        "machine the operator scanned. Leave it out for questions about the "
                        "customer's commercial relationship in general — a quote for a "
                        "machine that has not been installed yet belongs to the customer "
                        "and to no machine, so it is only found with this off."
                    ),
                },
                "quote_id": {
                    "type": "string",
                    "description": (
                        "Exact quote id, only when the user mentioned one, e.g. 'QTE-2025-0001'"
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "Draft",
                        "Submitted",
                        "Superseded",
                        "Approved",
                        "Rejected",
                        "Expired",
                    ],
                    "description": (
                        "Filter by the CURRENT status of the quote, which is the status of its "
                        "latest revision. Only when the user asked about a specific one "
                        "(e.g. 'which offers were rejected?')"
                    ),
                },
            },
            "required": [],
        },
    },
}

TOOLS = [SEARCH_ORDERS_TOOL, SEARCH_QUOTES_TOOL]
