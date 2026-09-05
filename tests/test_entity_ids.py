"""Object-ID strategy tests for multi-territory readiness."""

from __future__ import annotations

import pytest

from custom_components.eversource_rates.const import DOMAIN
from custom_components.eversource_rates.entity_ids import (
    sensor_object_id,
    slugify_object_id_part,
)


@pytest.mark.parametrize(
    ("sensor_key", "expected"),
    [
        ("supply_rate", "eversource_supply_rate"),
        ("delivery_rate", "eversource_delivery_rate"),
        ("total_electricity_rate", "eversource_total_electricity_rate"),
        ("customer_charge", "eversource_customer_charge"),
        ("distribution_charge", "eversource_distribution_charge"),
        ("system_benefits_charge", "eversource_system_benefits_charge"),
    ],
)
def test_nh_rate_r_object_ids_remain_legacy(sensor_key: str, expected: str) -> None:
    """Preserve the documented NH Rate R entity object IDs exactly."""
    assert sensor_object_id("nh", "r", sensor_key) == expected


def test_synthetic_ct_rate_classes_include_territory_and_do_not_collide() -> None:
    """CT rate classes must not share object IDs."""
    rate_1 = sensor_object_id("ct", "1", "total_electricity_rate")
    rate_7 = sensor_object_id("ct", "7", "total_electricity_rate")
    assert rate_1 == "eversource_ct_1_total_electricity_rate"
    assert rate_7 == "eversource_ct_7_total_electricity_rate"
    assert rate_1 != rate_7


def test_ct_rate_1_primary_sensor_object_ids_are_prefixed() -> None:
    """Supported CT Rate 1 uses territory/rate-class prefixed object IDs."""
    assert (
        sensor_object_id("ct", "1", "total_electricity_rate")
        == "eversource_ct_1_total_electricity_rate"
    )
    assert sensor_object_id("ct", "1", "supply_rate") == "eversource_ct_1_supply_rate"
    assert (
        sensor_object_id("ct", "1", "delivery_rate") == "eversource_ct_1_delivery_rate"
    )
    assert (
        sensor_object_id("ct", "1", "customer_charge")
        == "eversource_ct_1_customer_charge"
    )


def test_synthetic_ema_and_wma_r1_do_not_collide() -> None:
    """Distinct MA territories with the same rate class must not collide."""
    ema = sensor_object_id(
        "ema", "r1", "total_electricity_rate", supply_plan="fixed", service_area="main"
    )
    wma = sensor_object_id("wma", "r1", "total_electricity_rate", supply_plan="fixed")
    assert ema == "eversource_ema_r1_fixed_main_total_electricity_rate"
    assert wma == "eversource_wma_r1_fixed_total_electricity_rate"
    assert ema != wma


def test_wma_supply_plans_do_not_collide() -> None:
    """Fixed and Monthly Variable WMA entries must not share object IDs."""
    fixed = sensor_object_id("wma", "r1", "total_electricity_rate", supply_plan="fixed")
    monthly = sensor_object_id(
        "wma", "r1", "total_electricity_rate", supply_plan="monthly_variable"
    )
    assert fixed == "eversource_wma_r1_fixed_total_electricity_rate"
    assert monthly == "eversource_wma_r1_monthly_variable_total_electricity_rate"
    assert fixed != monthly


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rate 1", "rate_1"),
        ("r1-hp", "r1_hp"),
        ("System Benefits Charge", "system_benefits_charge"),
        ("  Total.Electricity/Rate  ", "total_electricity_rate"),
    ],
)
def test_slug_normalization_is_deterministic(raw: str, expected: str) -> None:
    """Punctuation and spacing normalize to stable object-ID parts."""
    assert slugify_object_id_part(raw) == expected
    assert sensor_object_id("ct", raw, "supply_rate").endswith(
        f"_{expected}_supply_rate"
    )


def test_slugify_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Cannot derive"):
        slugify_object_id_part("   ***  ")

    """Entity unique IDs remain domain_territory_rate_class_key."""
    territory = "nh"
    rate_class = "r"
    key = "total_electricity_rate"
    unique_id = "_".join((DOMAIN, territory, rate_class, key))
    assert unique_id == "eversource_rates_nh_r_total_electricity_rate"
    assert (
        sensor_object_id(territory, rate_class, key)
        == "eversource_total_electricity_rate"
    )
