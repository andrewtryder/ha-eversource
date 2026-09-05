"""Shared Home Assistant test configuration."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from custom_components.eversource_rates.models import (
    DeliveryComponent,
    DeliveryRates,
    EversourceRates,
    SupplyRate,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom components in each Home Assistant test."""
    yield


@pytest.fixture
def rates() -> EversourceRates:
    """Return a realistic immutable NH Rate R tariff snapshot."""
    components = {
        "distribution_charge": DeliveryComponent(
            "distribution_charge", "Distribution Charge", Decimal("0.06727")
        ),
        "regulatory_reconciliation_adjustment": DeliveryComponent(
            "regulatory_reconciliation_adjustment",
            "Regulatory Reconciliation Adjustment",
            Decimal("0.00296"),
        ),
        "pole_plant_adjustment": DeliveryComponent(
            "pole_plant_adjustment", "Pole Plant Adjustment", Decimal("-0.00029")
        ),
        "transmission_charge": DeliveryComponent(
            "transmission_charge", "Transmission Charge", Decimal("0.04445")
        ),
        "stranded_cost_recovery_charge": DeliveryComponent(
            "stranded_cost_recovery_charge",
            "Stranded Cost Recovery Charge",
            Decimal("-0.00148"),
        ),
        "system_benefits_charge": DeliveryComponent(
            "system_benefits_charge", "System Benefits Charge", Decimal("0.00618")
        ),
    }
    return EversourceRates(
        territory="nh",
        rate_class="r",
        supply=SupplyRate(Decimal("0.14009"), date(2026, 8, 1), date(2027, 1, 31), "r"),
        delivery=DeliveryRates(Decimal("19.81"), components),
        source_supply_url="https://example.test/supply",
        source_delivery_url="https://example.test/delivery",
        retrieved_at=datetime(2026, 9, 5, tzinfo=UTC),
    )
