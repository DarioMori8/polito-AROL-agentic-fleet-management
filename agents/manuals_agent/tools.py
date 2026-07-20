SEARCH_MANUAL_TOOL = {
    "type": "function",
    "function": {
        "name": "search_manual",
        "description": (
            "Search the machine's technical manual for passages relevant to a query. "
            "Returns the most relevant text excerpts, each with its source page number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A focused search query describing what to look for in the manual",
                }
            },
            "required": ["query"],
        },
    },
}

TOOLS = [SEARCH_MANUAL_TOOL]
