class AgentSwarmError(Exception):
    """Base exception class for all AgentSwarm errors"""

    pass


class ValidationError(AgentSwarmError):
    """Invalid input or validation failure"""

    pass


class AuthenticationError(AgentSwarmError):
    """API key missing or invalid"""

    pass


class RateLimitError(AgentSwarmError):
    """Too many requests - rate limit exceeded"""

    pass


class TimeoutError(AgentSwarmError):
    """LLM request timed out"""

    pass


class ProviderError(AgentSwarmError):
    """LLM provider returned non-rate-limit error"""

    pass


class StorageError(AgentSwarmError):
    """Cannot save or load conversation"""

    pass


class VerificationError(AgentSwarmError):
    """Fact-checking failed"""

    pass


class PartialResultError(AgentSwarmError):
    """Some results missing, returning best-effort"""

    pass


class FatalError(AgentSwarmError):
    """Unrecoverable error"""

    pass
