class AgentUnavailableError(Exception):
    """Sollevata quando un agente non risponde correttamente (timeout, down, errore HTTP)."""
    pass