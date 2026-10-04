"""Maps google-genai / google-auth exceptions to Forge's provider-independent LLM errors (D-150)."""

from __future__ import annotations

import httpx
from google.auth import exceptions as auth_exceptions
from google.genai import errors

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
from forge.net import connection_hint, root_cause
from forge.safety.redact import default_redactor

# What the SDK can raise for a call; anything else is a bug and must not be disguised as a provider failure.
SDK_ERRORS: tuple[type[BaseException], ...] = (
    errors.APIError,
    auth_exceptions.GoogleAuthError,
    httpx.HTTPError,
)

_CONTEXT_MARKERS = ("exceeds the maximum number of tokens", "input token count", "too long", "context window")
ADC_HELP = (
    "Gemini on Vertex AI uses Application Default Credentials; none were found or they were refused. "
    "Next step: run `gcloud auth application-default login` (or set GOOGLE_APPLICATION_CREDENTIALS to a "
    "service-account file) on this machine"
)


def map_gemini_error(error: BaseException) -> LLMError:
    message = default_redactor.redact(str(error))[:800]
    if isinstance(error, auth_exceptions.GoogleAuthError):
        return LLMAuthError(f"{ADC_HELP}: {message}")
    if isinstance(error, httpx.TimeoutException):
        return LLMConnectionError(f"Request timed out: {message}")
    if isinstance(error, httpx.HTTPError):
        cause = default_redactor.redact(root_cause(error))[:400]
        return LLMConnectionError(
            f"Could not reach Vertex AI: {message} Cause: {cause}. Next step: {connection_hint(cause)}."
        )
    if not isinstance(error, errors.APIError):
        return LLMError(message)

    status = error.code
    lowered = message.lower()
    if status == 429:
        return LLMRateLimitError(message)  # no Retry-After on this API; Forge's exponential backoff applies
    if status in (401, 403):
        return LLMAuthError(
            f"Vertex AI refused the credentials ({status}). {ADC_HELP}: {message}", status_code=status
        )
    if status == 404:
        # A Model Garden listing is not proof the project can call a model; only a live call is.
        return LLMNotFoundError(
            f"Model not found or not enabled for this project: {message}", status_code=status
        )
    if status == 400 and any(marker in lowered for marker in _CONTEXT_MARKERS):
        return LLMContextLengthError(message, status_code=status)
    if "safety" in lowered and "block" in lowered:
        return LLMContentFilterError(f"Blocked by Gemini's safety filter: {message}", status_code=status)
    if status >= 500 or status in (408, 409):
        return LLMServerError(message, status_code=status)
    return LLMBadRequestError(message, status_code=status)
