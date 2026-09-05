"""Fetch the public NH Rate R tariff; intended for manual developer verification."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.eversource_rates.api import EversourceClient
from custom_components.eversource_rates.models import EversourceRates
from custom_components.eversource_rates.parser import (
    EversourceParseError,
    parse_delivery_html as _parse_delivery,
    parse_supply_html as _parse_supply,
)


class TariffParseError(EversourceParseError):
    """Compatibility error exposed by this developer utility."""


@dataclass(frozen=True)
class TariffRates:
    supply_rate: Decimal
    delivery_rate: Decimal
    total_variable_rate: Decimal
    monthly_customer_charge: Decimal
    delivery_components: Mapping[str, Decimal]
    supply_effective_start: str | None
    supply_effective_end: str | None
    retrieval_timestamp: str
    supply_source_url: str
    delivery_source_url: str

    def to_dict(self) -> dict[str, object]:
        return {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in self.__dict__.items()
        }


def _display_date(value) -> str | None:
    """Format a date portably as ``September 5, 2026`` (no platform-specific flags)."""
    if not value:
        return None
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def parse_supply_html(html: str) -> tuple[Decimal, str | None, str | None]:
    try:
        supply = _parse_supply(html)
    except EversourceParseError as err:
        raise TariffParseError(str(err)) from err
    return (
        supply.rate,
        _display_date(supply.effective_date),
        _display_date(supply.expiration_date),
    )


def parse_delivery_html(html: str) -> tuple[Decimal, Decimal, dict[str, Decimal]]:
    try:
        delivery = _parse_delivery(html)
    except EversourceParseError as err:
        raise TariffParseError(str(err)) from err
    return (
        delivery.customer_charge,
        delivery.variable_rate,
        {key: item.rate for key, item in delivery.variable_components.items()},
    )


def _from_rates(rates: EversourceRates) -> TariffRates:
    return TariffRates(
        rates.supply.rate,
        rates.delivery.variable_rate,
        rates.total_variable_rate,
        rates.delivery.customer_charge,
        {key: item.rate for key, item in rates.delivery.variable_components.items()},
        _display_date(rates.supply.effective_date),
        _display_date(rates.supply.expiration_date),
        rates.retrieved_at.isoformat(),
        rates.source_supply_url,
        rates.source_delivery_url,
    )


def validate_rates(rates: TariffRates) -> None:
    if not Decimal("0") < rates.supply_rate < Decimal("1"):
        raise TariffParseError("Supply rate outside plausible range")
    if not Decimal("0") < rates.delivery_rate < Decimal("1"):
        raise TariffParseError("Delivery rate outside plausible range")
    if not Decimal("0") < rates.total_variable_rate < Decimal("2"):
        raise TariffParseError("Total variable rate outside plausible range")
    if not Decimal("0") < rates.monthly_customer_charge < Decimal("200"):
        raise TariffParseError("Customer charge outside plausible range")


async def fetch_eversource_rates(**_: object) -> TariffRates:
    """Fetch without authentication using only Cookie: .SEGMENT=nh."""
    async with aiohttp.ClientSession() as session:
        client = EversourceClient(
            session,
            territory="nh",
            segment="nh",
            rate_class="r",
        )
        return _from_rates(await client.async_get_rates())


async def main() -> None:
    rates = await fetch_eversource_rates()
    print("Territory: New Hampshire\nRate class: R")
    print(f"Supply: ${rates.supply_rate}/kWh\nDelivery: ${rates.delivery_rate}/kWh")
    print(
        f"Total variable: ${rates.total_variable_rate}/kWh\n"
        f"Customer charge: ${rates.monthly_customer_charge}/month"
    )
    print(
        f"Supply effective: {rates.supply_effective_start}\n"
        f"Supply expires: {rates.supply_effective_end}"
    )


if __name__ == "__main__":
    asyncio.run(main())
