"""Versioned server-side prices; unknown usage or model identity is not free."""

from dataclasses import dataclass
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
        if price is None or model != price.model or not valid_usage(usage):
            return None
        return (
            (usage.input_tokens - usage.cached_input_tokens) * price.input_per_million
            + usage.cached_input_tokens * price.cached_input_per_million
            + usage.output_tokens * price.output_per_million
        ) / Decimal(1_000_000)


def valid_usage(usage: TokenUsage | None) -> bool:
    return (
        usage is not None
        and all(type(count) is int and count >= 0
                for count in (usage.input_tokens, usage.output_tokens, usage.cached_input_tokens))
        and usage.cached_input_tokens <= usage.input_tokens
        and (usage.reasoning_tokens is None or type(usage.reasoning_tokens) is int
             and 0 <= usage.reasoning_tokens <= usage.output_tokens)
    )


@dataclass(frozen=True)
class AzureModelProfile:
    identifier: str
    model: str
    version: str
    sku: str
    region: str
    max_input_tokens: int
    max_output_tokens: int
    reasoning_effort: str
    image_detail: str
    service_tier: str
    price_version: str
    price: DeploymentPrice

    def reserve_usd(self, output_tokens: int) -> Decimal:
        if type(output_tokens) is not int or not 1 <= output_tokens <= self.max_output_tokens:
            raise ValueError("Output cap exceeds the reviewed model profile.")
        return (
            self.max_input_tokens * max(self.price.input_per_million, self.price.cached_input_per_million)
            + output_tokens * self.price.output_per_million
        ) / Decimal(1_000_000)


GPT_54_MINI = AzureModelProfile(
    identifier="gpt-5.4-mini-2026-03-17-dz-v1",
    model="gpt-5.4-mini", version="2026-03-17", sku="DataZoneStandard", region="swedencentral",
    max_input_tokens=272_000, max_output_tokens=2_000,
    reasoning_effort="none", image_detail="high", service_tier="default",
    price_version="azure-sweden-dz-2026-09-18-v1",
    price=DeploymentPrice(
        model="gpt-5.4-mini-2026-03-17", input_per_million=Decimal("0.825"),
        cached_input_per_million=Decimal("0.0825"), output_per_million=Decimal("4.95"),
    ),
)


def resolve_profiles(bindings: dict[str, str], routes: dict[str, str], prices: PriceTable | None,
                     max_output_tokens: int) -> dict[str, AzureModelProfile]:
    if not bindings:
        if prices and any(price.model.startswith("gpt-5.4-mini") for price in prices.deployments.values()):
            raise ValueError("GPT-5.4-mini requires an explicit reviewed deployment profile.")
        return {}
    if (set(bindings) != set(routes.values()) or prices is None
            or set(prices.deployments) != set(bindings) or prices.version != GPT_54_MINI.price_version
            or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= GPT_54_MINI.max_output_tokens):
        raise ValueError("Deployment routes, prices and output cap must match the reviewed profile.")
    if any(profile != GPT_54_MINI.identifier or prices.deployments[deployment] != GPT_54_MINI.price
           for deployment, profile in bindings.items()):
        raise ValueError("Unknown profile or mismatched model/prices.")
    return {deployment: GPT_54_MINI for deployment in bindings}