"""Normalized gateway errors.

Provider-specific detail (provider name, model, raw transport errors) must
never leak through these error types into HTTP responses. Every route-level
error must ultimately be one of these types; see app.main for the final
catch-all boundary that normalizes anything else.
"""

from __future__ import annotations


class GatewayError(Exception):
    """Base class for normalized, public-safe gateway errors."""

    code = "gateway_error"
    http_status = 500

    def __init__(self, message: str = "An unexpected gateway error occurred."):
        super().__init__(message)
        self.message = message


class AuthenticationRequiredError(GatewayError):
    code = "authentication_required"
    http_status = 401

    def __init__(self) -> None:
        super().__init__("Authentication is required to call this endpoint.")


class RequestValidationFailedError(GatewayError):
    code = "request_invalid"
    http_status = 422

    def __init__(self, message: str = "The request failed validation.") -> None:
        super().__init__(message)


class ProviderRateLimitedError(GatewayError):
    """Reserved for a provider signaling rate limiting.

    Not raised by FakeProvider today; kept so the future Copilot SDK
    adapter has a normalized target instead of inventing a new error shape.
    """

    code = "provider_rate_limited"
    http_status = 429

    def __init__(self) -> None:
        super().__init__("The AI provider is rate limiting requests.")


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


class InternalGatewayError(GatewayError):
    """Final, safe fallback for any exception not otherwise normalized."""

    code = "internal_error"
    http_status = 500

    def __init__(self) -> None:
        super().__init__("An unexpected gateway error occurred.")
