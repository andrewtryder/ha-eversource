"""Territory-specific public tariff parsers with dispatch."""

from __future__ import annotations

from collections.abc import Callable

from ..models import DeliveryRates, SupplyRate
from ..tariffs import TariffSelection
from . import ct, ma, nh
from .common import EversourceParseError

__all__ = [
    "EversourceParseError",
    "get_tariff_parser",
    "parse_tariff",
]


def get_tariff_parser(
    selection: TariffSelection,
) -> tuple[
    Callable[[str], SupplyRate],
    Callable[[str], DeliveryRates],
]:
    """Return ``(parse_supply, parse_delivery)`` for a tariff selection."""
    match (selection.territory, selection.rate_class):
        case ("nh", "r"):

            def parse_nh_supply(html: str) -> SupplyRate:
                return nh.parse_supply_html(html, selection.rate_class)

            return parse_nh_supply, nh.parse_delivery_html
        case ("ct", "1"):

            def parse_ct_supply(html: str) -> SupplyRate:
                return ct.parse_supply_html(html, selection.rate_class)

            return parse_ct_supply, ct.parse_delivery_html
        case ("wma", "r1") | ("ema", "r1"):

            def parse_ma_supply(html: str) -> SupplyRate:
                return ma.parse_supply_html(html, selection)

            def parse_ma_delivery(html: str) -> DeliveryRates:
                return ma.parse_delivery_html(html, selection)

            return parse_ma_supply, parse_ma_delivery
        case _:
            raise EversourceParseError(
                f"No tariff parser for {selection.territory!r}/{selection.rate_class!r}"
            )


def parse_tariff(
    selection: TariffSelection,
    supply_html: str,
    delivery_html: str,
) -> tuple[SupplyRate, DeliveryRates]:
    """Parse supply and delivery HTML for one logical tariff identity."""
    parse_supply, parse_delivery = get_tariff_parser(selection)
    return parse_supply(supply_html), parse_delivery(delivery_html)
