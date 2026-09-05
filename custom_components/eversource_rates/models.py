"""Immutable tariff data models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SupplyRate:
    """The current variable supply rate and its public effective period."""

    rate: Decimal
    effective_date: date | None
    expiration_date: date | None
    rate_class: str


@dataclass(frozen=True, slots=True)
class DeliveryComponent:
    """One variable delivery charge identified in the public tariff table."""

    key: str
    label: str
    rate: Decimal
    unit: str = "USD/kWh"


@dataclass(frozen=True, slots=True)
class DeliveryRates:
    """Fixed customer charge and variable delivery riders."""

    customer_charge: Decimal
    variable_components: Mapping[str, DeliveryComponent]

    def __post_init__(self) -> None:
        """Defensively freeze the input component mapping."""
        object.__setattr__(
            self,
            "variable_components",
            MappingProxyType(dict(self.variable_components)),
        )

    @property
    def variable_rate(self) -> Decimal:
        """Return the exact sum of all per-kWh delivery components."""
        return sum(
            (item.rate for item in self.variable_components.values()), Decimal("0")
        )


@dataclass(frozen=True, slots=True)
class EversourceRates:
    """An immutable snapshot of one public Eversource tariff."""

    territory: str
    rate_class: str
    supply: SupplyRate
    delivery: DeliveryRates
    source_supply_url: str
    source_delivery_url: str
    retrieved_at: datetime

    @property
    def total_variable_rate(self) -> Decimal:
        """Return supply plus variable delivery, excluding the customer charge."""
        return self.supply.rate + self.delivery.variable_rate
