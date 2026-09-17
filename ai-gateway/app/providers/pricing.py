"""Versioned server-side prices; unknown usage or model identity is not free."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.providers.base import TokenUsage

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")]
Rate = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class DeploymentPrice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Identifier
    input_per_million: Rate
    cached_input_per_million: Rate
    output_per_million: Rate


class PriceTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Identifier
    currency: Literal["USD"]
    deployments: dict[Identifier, DeploymentPrice]

    def estimate(self, deployment: str, model: str | None, usage: TokenUsage | None) -> Decimal | None:
        price = self.deployments.get(deployment)
        if price is None or model != price.model or usage is None or usage.cached_input_tokens is None:
            return None
        return (
            (usage.input_tokens - usage.cached_input_tokens) * price.input_per_million
            + usage.cached_input_tokens * price.cached_input_per_million
            + usage.output_tokens * price.output_per_million
        ) / Decimal(1_000_000)