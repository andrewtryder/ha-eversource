"""Territory-specific public tariff parsers with dispatch."""

from __future__ import annotations

from ..models import DeliveryRates, SupplyRate
from . import ct, nh
from .common import EversourceParseError

__all__ = [
    "EversourceParseError",
    "get_tariff_parser",
    "parse_tariff",
]


def get_tariff_parser(territory: str, rate_class: str):
    """Return ``(parse_supply, parse_delivery)`` for a supported tariff pair."""
    match (territory, rate_class):
        case ("nh", "r"):
            return nh.parse_supply_html, nh.parse_delivery_html
        case ("ct", "1"):
            return ct.parse_supply_html, ct.parse_delivery_html
        case _:
            raise EversourceParseError(
                f"No tariff parser for {territory!r}/{rate_class!r}"
            )


def parse_tariff(
    territory: str,
    rate_class: str,
    supply_html: str,
    delivery_html: str,
) -> tuple[SupplyRate, DeliveryRates]:
    """Parse supply and delivery HTML for one logical tariff identity."""
    parse_supply, parse_delivery = get_tariff_parser(territory, rate_class)
    return parse_supply(supply_html, rate_class), parse_delivery(delivery_html)
