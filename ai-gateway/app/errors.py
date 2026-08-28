"""Normalized gateway errors.

Provider-specific detail (provider name, model, raw transport errors) must
never leak through these error types into HTTP responses.
"""

from __future__ import annotations


class GatewayError(Exception):
    """Base class for normalized, public-safe gateway errors."""

    code = "gateway_error"
    http_status = 500

    def __init__(self, message: str = "An unexpected gateway error occurred."):
        super().__init__(message)
        self.message = message


class ProviderTimeoutError(GatewayError):
    code = "provider_timeout"
    http_status = 504

    def __init__(self) -> None:
        super().__init__("The AI provider did not respond in time.")


class ProviderUnavailableError(GatewayError):
    code = "provider_unavailable"
    http_status = 502

    def __init__(self) -> None:
        super().__init__("The AI provider is currently unavailable.")


class ProviderOutputInvalidError(GatewayError):
    code = "provider_output_invalid"
    http_status = 502

    def __init__(self) -> None:
        super().__init__("The AI provider returned output that failed validation.")


class RequestValidationFailedError(GatewayError):
    code = "request_invalid"
    http_status = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
