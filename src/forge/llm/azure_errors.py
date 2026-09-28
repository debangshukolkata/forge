"""Maps OpenAI SDK exceptions to Forge's provider-independent LLM errors."""

from __future__ import annotations

from typing import Any

import openai

from forge.errors import (
    LLMAuthError,
    LLMBadRequestError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMContextLengthError,
    LLMError,
    LLMNotFoundError,
    LLMRateLimitError,
    LLMServerError,
)
from forge.safety.redact import default_redactor

_CONTEXT_MARKERS = (
    "context_length_exceeded",
    "maximum context length",
    "too many tokens",
    "string_above_max_length",
)
_FILTER_MARKERS = ("content_filter", "responsibleaipolicyviolation", "content management policy")


def map_openai_error(error: Exception) -> LLMError:
    message = default_redactor.redact(str(error))[:800]
    if isinstance(error, openai.APITimeoutError):
        return LLMConnectionError(f"Request timed out: {message}")
    if isinstance(error, openai.APIConnectionError):
        return LLMConnectionError(f"Could not reach the endpoint: {message}")
    if not isinstance(error, openai.APIStatusError):
        return LLMError(message)

    status = error.status_code
    lowered = message.lower() + " " + _error_code(error.body).lower()
    if status == 429:
        return LLMRateLimitError(message, retry_after_s=retry_after_seconds(error.response.headers))
    if status in (401, 403):
        return LLMAuthError(
            f"Authentication failed ({status}); check the key and endpoint: {message}", status_code=status
        )
    if status == 404:
        return LLMNotFoundError(message, status_code=status)
    if any(marker in lowered for marker in _CONTEXT_MARKERS):
        return LLMContextLengthError(message, status_code=status)
    if any(marker in lowered for marker in _FILTER_MARKERS):
        return LLMContentFilterError(f"Blocked by the Azure content filter: {message}", status_code=status)
    if status >= 500 or status in (408, 409):
        return LLMServerError(message, status_code=status)
    return LLMBadRequestError(message, status_code=status)


def retry_after_seconds(headers: Any) -> float | None:
    for name, scale in (("retry-after-ms", 1000.0), ("x-ms-retry-after-ms", 1000.0), ("retry-after", 1.0)):
        value = headers.get(name) if headers is not None else None
        if value is None:
            continue
        try:
            return float(value) / scale
        except ValueError:
            continue  # HTTP-date form of Retry-After; fall back to exponential backoff
    return None


def _error_code(body: object) -> str:
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict):
            return f"{inner.get('code') or ''} {inner.get('type') or ''}"
    return ""
