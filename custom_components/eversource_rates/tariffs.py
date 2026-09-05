"""Tariff identity definitions and selection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_RATE_CLASS,
    CONF_SERVICE_AREA,
    CONF_SUPPLY_PLAN,
    CONF_TERRITORY,
    DOMAIN,
)


@dataclass(frozen=True, slots=True)
class TariffDefinition:
    """Metadata describing one supported territory/rate-class product."""

    territory: str
    rate_class: str
    name: str
    supply_plans: tuple[str, ...] = ()
    service_areas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TariffSelection:
    """A fully resolved tariff identity chosen during config."""

    territory: str
    rate_class: str
    supply_plan: str | None = None
    service_area: str | None = None


TARIFF_DEFINITIONS: dict[tuple[str, str], TariffDefinition] = {
    ("nh", "r"): TariffDefinition("nh", "r", "Residential Rate R"),
    ("ct", "1"): TariffDefinition("ct", "1", "Rate 1 - Residential"),
    ("wma", "r1"): TariffDefinition(
        "wma",
        "r1",
        "R1 - Residential Non-Heating",
        supply_plans=("fixed", "monthly_variable"),
    ),
}

SUPPLY_PLAN_NAMES = {
    "fixed": "Fixed Basic Service",
    "monthly_variable": "Monthly Variable Basic Service",
}

SERVICE_AREA_NAMES = {
    "main": "Greater Boston / Cambridge / South Shore",
    "cape": "Cape Cod / Martha's Vineyard",
}


def get_tariff_definition(territory: str, rate_class: str) -> TariffDefinition | None:
    """Return the tariff definition for a territory/rate class, if any."""
    return TARIFF_DEFINITIONS.get((territory, rate_class))


def selection_from_entry_data(data: dict[str, Any]) -> TariffSelection:
    """Build a TariffSelection from config-entry data."""
    return TariffSelection(
        territory=data[CONF_TERRITORY],
        rate_class=data[CONF_RATE_CLASS],
        supply_plan=data.get(CONF_SUPPLY_PLAN),
        service_area=data.get(CONF_SERVICE_AREA),
    )


def entry_unique_id(selection: TariffSelection) -> str:
    """Return the config-entry unique id for a tariff selection."""
    parts = [DOMAIN, selection.territory, selection.rate_class]
    if selection.supply_plan:
        parts.append(selection.supply_plan)
    if selection.service_area:
        parts.append(selection.service_area)
    return "_".join(parts)


def selection_identity_parts(selection: TariffSelection) -> tuple[str, ...]:
    """Return slug parts used in entity unique/object ids after territory/rate."""
    parts: list[str] = []
    if selection.supply_plan:
        parts.append(selection.supply_plan)
    if selection.service_area:
        parts.append(selection.service_area)
    return tuple(parts)
