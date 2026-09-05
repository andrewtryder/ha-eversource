"""Constants and supported-tariff definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

DOMAIN = "eversource_rates"
CONF_TERRITORY = "territory"
CONF_RATE_CLASS = "rate_class"
UPDATE_INTERVAL = timedelta(hours=12)
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
}
RATE_CLASS_NAMES = {"r": "Residential Rate R"}
