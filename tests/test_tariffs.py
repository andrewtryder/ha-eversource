"""Tariff definition and selection helper tests."""

from __future__ import annotations

from custom_components.eversource_rates.const import (
    CONF_RATE_CLASS,
    CONF_SERVICE_AREA,
    CONF_SUPPLY_PLAN,
    CONF_TERRITORY,
)
from custom_components.eversource_rates.tariffs import (
    TariffSelection,
    entry_unique_id,
    get_tariff_definition,
    selection_from_entry_data,
    selection_identity_parts,
)


def test_selection_from_entry_data_includes_optional_dimensions() -> None:
    selection = selection_from_entry_data(
        {
            CONF_TERRITORY: "ema",
            CONF_RATE_CLASS: "r1",
            CONF_SUPPLY_PLAN: "fixed",
            CONF_SERVICE_AREA: "cape",
        }
    )
    assert selection == TariffSelection("ema", "r1", "fixed", "cape")
    assert entry_unique_id(selection) == "eversource_rates_ema_r1_fixed_cape"
    assert selection_identity_parts(selection) == ("fixed", "cape")


def test_nh_definition_has_no_extra_dimensions() -> None:
    definition = get_tariff_definition("nh", "r")
    assert definition is not None
    assert definition.supply_plans == ()
    assert definition.service_areas == ()
    assert entry_unique_id(TariffSelection("nh", "r")) == "eversource_rates_nh_r"
    assert selection_identity_parts(TariffSelection("nh", "r")) == ()


def test_wma_definition_requires_supply_plans() -> None:
    definition = get_tariff_definition("wma", "r1")
    assert definition is not None
    assert definition.supply_plans == ("fixed", "monthly_variable")
    assert definition.service_areas == ()


def test_ema_definition_requires_supply_plan_and_service_area() -> None:
    definition = get_tariff_definition("ema", "r1")
    assert definition is not None
    assert definition.supply_plans == ("fixed", "monthly_variable")
    assert definition.service_areas == ("main", "cape")
