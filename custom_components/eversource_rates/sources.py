"""Public tariff fetch definitions (URLs and optional Sitefinity segment)."""

from __future__ import annotations

from dataclasses import dataclass

from .const import DELIVERY_URL, SUPPLY_URL


@dataclass(frozen=True, slots=True)
class TariffSource:
    """Where to fetch one supported public tariff."""

    supply_url: str
    delivery_url: str
    segment: str | None = None  # Cookie only when needed


# NH keeps the proven generic URLs + segment cookie. CT uses territory-suffixed
# public URLs without a cookie (cookie-only generic URLs were unreliable for CT).
TARIFF_SOURCES: dict[tuple[str, str], TariffSource] = {
    ("nh", "r"): TariffSource(SUPPLY_URL, DELIVERY_URL, segment="nh"),
    ("ct", "1"): TariffSource(
        f"{SUPPLY_URL}/ct",
        f"{DELIVERY_URL}/ct",
        segment=None,
    ),
    ("wma", "r1"): TariffSource(
        f"{SUPPLY_URL}/wma",
        f"{DELIVERY_URL}/wma",
        segment=None,
    ),
}


def get_tariff_source(territory: str, rate_class: str) -> TariffSource | None:
    """Return the fetch definition for a logical territory/rate class, if any."""
    return TARIFF_SOURCES.get((territory, rate_class))
