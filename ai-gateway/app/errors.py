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


class ProviderAuthenticationError(GatewayError):
    """The provider rejected our credentials/session (never exposes which)."""

    code = "provider_authentication_failed"
    http_status = 502

    def __init__(self) -> None:
        super().__init__("The AI provider rejected the gateway's credentials.")


class ModelUnavailableError(GatewayError):
    """The configured model/purpose is not available; never substituted silently."""

    code = "model_unavailable"
    http_status = 502

    def __init__(self) -> None:
        super().__init__("The configured AI model is not currently available.")


class ServiceNotReadyError(GatewayError):
    """Raised by /readyz when the configured provider is not ready.

    Distinct from ProviderUnavailableError (502, raised for a request-time
    provider failure): this is a readiness-specific 503 so callers can
    distinguish "not ready to serve" from "a request failed".
    """

    code = "service_not_ready"
    http_status = 503

    def __init__(self) -> None:
        super().__init__("The gateway is not ready to serve requests.")


class ProviderOutputInvalidError(GatewayError):
    code = "provider_output_invalid"
    http_status = 502

    def __init__(self) -> None:
        super().__init__("The AI provider returned output that failed validation.")


class ServiceSaturatedError(GatewayError):
    """Raised when the configured concurrency limit is already in use.

    Fails fast rather than queuing unbounded work in memory: the caller
    should retry later, not be made to wait indefinitely.
    """

    code = "service_saturated"
    http_status = 503

    def __init__(self) -> None:
        super().__init__("The gateway is at its concurrent request limit. Try again shortly.")


class InternalGatewayError(GatewayError):
    """Final, safe fallback for any exception not otherwise normalized."""

    code = "internal_error"
    http_status = 500

    def __init__(self) -> None:
        super().__init__("An unexpected gateway error occurred.")
