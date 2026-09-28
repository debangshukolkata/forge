"""Exception hierarchy. Tools and UIs catch these; nothing else in Forge raises bare Exception."""

from __future__ import annotations


class ForgeError(Exception):
    """Base class for every error Forge raises on purpose."""


class ConfigError(ForgeError):
    """Invalid or missing configuration (config.yaml, .env, role/model mapping)."""


class BudgetExceededError(ForgeError):
    """The session budget cap was reached; the user must approve continuing."""


class LLMError(ForgeError):
    """Base class for provider failures, already normalised across providers."""

    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMRateLimitError(LLMError):
    retryable = True
    retry_after_s: float | None

    def __init__(
        self, message: str, *, retry_after_s: float | None = None, status_code: int | None = 429
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after_s = retry_after_s


class LLMServerError(LLMError):
    retryable = True


class LLMConnectionError(LLMError):
    """Network failure or timeout before a response arrived."""

    retryable = True


class LLMContextLengthError(LLMError):
    """The request exceeded the model's context window (triggers emergency compaction, spec §10.4)."""


class LLMContentFilterError(LLMError):
    """Azure content filter blocked the prompt or the completion."""


class LLMAuthError(LLMError):
    """Bad key, wrong endpoint or missing permission."""


class LLMNotFoundError(LLMError):
    """Deployment or API route not found (e.g. Responses API on an old api-version)."""


class LLMBadRequestError(LLMError):
    """The provider rejected the request for another reason."""
