"""Provider-neutral abstraction for structured AI generation.

Every AI provider (the deterministic FakeProvider today, the future Copilot
SDK adapter) implements this interface. Use cases and routes depend only on
this abstraction, never on a concrete provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderRequest:
    """A provider-neutral request for one structured-generation task."""

    task: str
    payload: dict[str, Any]
    timeout_seconds: float


@dataclass(frozen=True)
class ProviderResponse:
    """A provider-neutral structured response.

    ``data`` is untyped at this layer; the calling use case is responsible
    for validating it against the appropriate public schema. Provider output
    is never trusted application data until it passes that validation.
    """

    data: dict[str, Any]


class StructuredGenerationProvider(ABC):
    """Provider-neutral contract for turning a task + payload into structured data."""

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute one structured-generation task.

        Implementations must raise the normalized errors from ``app.errors``
        (``ProviderTimeoutError``, ``ProviderUnavailableError``) rather than
        letting provider-specific exceptions escape.
        """
        raise NotImplementedError
