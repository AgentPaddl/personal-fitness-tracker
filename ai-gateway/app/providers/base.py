"""Provider-neutral abstraction for structured AI generation.

This module is intentionally domain-blind: it has no notion of "food",
"nutrition", or any other use case. Concrete providers (the deterministic
FakeProvider today, the future Copilot SDK adapter) only ever see generic
generation instructions, an optional model-routing purpose, a desired JSON
schema, optional attachments, and a timeout. All domain-specific
orchestration (what to ask for, which schema, how to interpret the result)
lives in use cases, never in a provider implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

#: A single generation instruction/message. "system" carries task framing,
#: "user" carries the actual content to analyze.
Role = Literal["system", "user"]


@dataclass(frozen=True)
class GenerationMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class Attachment:
    """An extensible, optional piece of multimodal input.

    ``kind`` and ``media_type`` are provider-transport concerns (e.g. an
    image attachment for a future multimodal request); ``data`` is left
    generic (e.g. base64 text or raw bytes) so new attachment kinds do not
    require changing this dataclass.
    """

    kind: str
    media_type: str
    data: str


@dataclass(frozen=True)
class StructuredGenerationRequest:
    """A provider-neutral request for one structured-generation call.

    ``model_purpose`` is an opaque, server-side routing key (see
    app.config) that a provider adapter may use to select a concrete model
    or deployment. It carries no domain semantics a provider must
    understand beyond "which configured route to use".

    ``output_json_schema`` is a plain JSON Schema dict (not a domain model
    class) describing the shape the caller wants back. Providers use it
    only as generation guidance; the calling use case is solely
    responsible for authoritative validation of the returned data.
    """

    model_purpose: str
    messages: list[GenerationMessage]
    output_json_schema: dict[str, Any]
    timeout_seconds: float
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredGenerationResult:
    """A provider-neutral structured result.

    ``data`` is untyped at this layer; the calling use case validates it
    against the appropriate public schema. Provider output is never trusted
    application data until it passes that validation.
    """

    data: dict[str, Any]


class StructuredGenerationProvider(ABC):
    """Provider-neutral contract for turning a generic request into structured data."""

    @abstractmethod
    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        """Execute one structured-generation call.

        Implementations must raise the normalized errors from ``app.errors``
        (``ProviderTimeoutError``, ``ProviderUnavailableError``,
        ``ProviderRateLimitedError``) rather than letting provider-specific
        exceptions escape.
        """
        raise NotImplementedError

    async def check_ready(self) -> bool:
        """Cheap readiness check.

        The default implementation assumes the provider is always ready.
        A real provider adapter should override this with a lightweight
        connectivity/auth check that does not perform a billed generation
        call (e.g. a session/handshake check rather than a full request).
        """
        return True
