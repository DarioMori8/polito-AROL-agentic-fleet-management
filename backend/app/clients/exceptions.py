class AgentUnavailableError(Exception):
    """
    Raised when a downstream agent cannot give a usable answer: timeout,
    service down, HTTP error status, or a response that does not match the
    expected schema. Tools catch it and turn it into an error artifact, so a
    failing agent never crashes the graph.
    """
    pass