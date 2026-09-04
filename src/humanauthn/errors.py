"""Errors raised by the HumanAuthn Python SDK."""

from __future__ import annotations


class HumanAuthnError(Exception):
    """Base class for all errors thrown by the SDK."""


class HumanAuthnConfigError(HumanAuthnError):
    """Thrown when the client is misconfigured or input is invalid."""


class HumanAuthnTimeoutError(HumanAuthnError):
    """Thrown when a request exceeds the configured timeout."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"Request timed out after {timeout}s")


class HumanAuthnApiError(HumanAuthnError):
    """Thrown when the API returns a non-2xx response."""

    def __init__(
        self,
        message: str,
        status: int,
        code: str | None = None,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details

    @property
    def is_auth_error(self) -> bool:
        """True for authentication/authorization failures (401/403)."""
        return self.status in {401, 403}

    @property
    def is_retryable(self) -> bool:
        """True for transient server errors worth retrying."""
        return self.status >= 500
