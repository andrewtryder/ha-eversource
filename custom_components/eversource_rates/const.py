"""Constants and supported-tariff definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

DOMAIN = "eversource_rates"
CONF_TERRITORY = "territory"
CONF_RATE_CLASS = "rate_class"
CONF_UPDATE_INTERVAL_HOURS = "update_interval_hours"
DEFAULT_UPDATE_INTERVAL_HOURS = 24
# Fixed select choices (hours). Minute-level polling is intentionally unsupported.
UPDATE_INTERVAL_HOUR_CHOICES: tuple[int, ...] = (6, 12, 24, 48, 72, 168)
REQUEST_TIMEOUT_SECONDS = 30

SUPPLY_URL = "https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates"
DELIVERY_URL = "https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates"


@dataclass(frozen=True, slots=True)
class Territory:
    """A publicly verified tariff territory."""

    key: str
    name: str
    segment: str
    supported_rate_classes: tuple[str, ...]


TERRITORIES = {
    "nh": Territory("nh", "New Hampshire", "nh", ("r",)),
    "ct": Territory("ct", "Connecticut", "ct", ("1",)),
}
RATE_CLASS_NAMES = {
    "r": "Residential Rate R",
    "1": "Rate 1 - Residential",
}


def update_interval_options() -> dict[int, str]:
    """Return selectable hour values mapped to English option labels."""
    return {
        6: "6 hours",
        12: "12 hours",
        24: "24 hours",
        48: "48 hours",
        72: "72 hours",
        168: "7 days",
    }


def update_interval_hours_from_options(options: dict[str, Any] | None) -> int:
    """Resolve polling hours from config-entry options (default 24)."""
    if not options:
        return DEFAULT_UPDATE_INTERVAL_HOURS
    raw = options.get(CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS)
    try:
        hours = int(raw)
    except TypeError, ValueError:
        return DEFAULT_UPDATE_INTERVAL_HOURS
    if hours not in UPDATE_INTERVAL_HOUR_CHOICES:
        return DEFAULT_UPDATE_INTERVAL_HOURS
    return hours


def update_interval_timedelta_from_options(options: dict[str, Any] | None) -> timedelta:
    """Resolve a coordinator ``update_interval`` from config-entry options."""
    return timedelta(hours=update_interval_hours_from_options(options))
