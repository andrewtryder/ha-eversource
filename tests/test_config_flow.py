"""Config-flow territory and rate-class filtering tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.eversource_rates.config_flow import _rate_class_options
from custom_components.eversource_rates.const import (
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    DOMAIN,
    RATE_CLASS_NAMES,
    TERRITORIES,
    Territory,
)


def _synthetic_territories() -> dict[str, Territory]:
    return {
        "alpha": Territory("alpha", "Alpha", "seg-alpha", ("r1", "r2")),
        "beta": Territory("beta", "Beta", "seg-beta", ("r3",)),
        "nh": Territory("nh", "New Hampshire", "nh", ("r",)),
    }


def _synthetic_rate_names() -> dict[str, str]:
    return {
        **RATE_CLASS_NAMES,
        "r1": "Rate 1",
        "r2": "Rate 2",
        "r3": "Rate 3",
    }


async def test_rate_class_options_are_filtered_by_territory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each territory only exposes its supported_rate_classes."""
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.TERRITORIES",
        _synthetic_territories(),
    )
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.RATE_CLASS_NAMES",
        _synthetic_rate_names(),
    )
    assert set(_rate_class_options("alpha")) == {"r1", "r2"}
    assert set(_rate_class_options("beta")) == {"r3"}
    assert "r3" not in _rate_class_options("alpha")
    assert "r1" not in _rate_class_options("beta")
    assert "r2" not in _rate_class_options("beta")


async def test_config_flow_two_step_nh_unchanged(hass: HomeAssistant, rates) -> None:
    """NH setup still stores territory/rate_class and unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "nh"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rate_class"

    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RATE_CLASS: "r"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"}
    assert result["result"].unique_id == "eversource_rates_nh_r"


async def test_config_flow_connecticut_rate_1(hass: HomeAssistant, rates) -> None:
    """Connecticut Rate 1 is selectable and creates a prefixed unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "ct"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rate_class"
    rate_validator = next(iter(result["data_schema"].schema.values()))
    assert set(rate_validator.container) == {"1"}

    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RATE_CLASS: "1"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TERRITORY: "ct", CONF_RATE_CLASS: "1"}
    assert result["result"].unique_id == "eversource_rates_ct_1"
    assert "Connecticut" in result["title"]
    assert "Rate 1" in result["title"]


async def test_config_flow_ema_requires_supply_plan_and_service_area(
    hass: HomeAssistant, rates
) -> None:
    """Eastern Massachusetts R1 asks for supply plan then service area."""
    from custom_components.eversource_rates.const import (
        CONF_SERVICE_AREA,
        CONF_SUPPLY_PLAN,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "ema"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_RATE_CLASS: "r1"}
    )
    assert result["step_id"] == "supply_plan"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SUPPLY_PLAN: "fixed"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "service_area"
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERVICE_AREA: "cape"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TERRITORY: "ema",
        CONF_RATE_CLASS: "r1",
        CONF_SUPPLY_PLAN: "fixed",
        CONF_SERVICE_AREA: "cape",
    }
    assert result["result"].unique_id == "eversource_rates_ema_r1_fixed_cape"
    assert "Eastern Massachusetts" in result["title"]
    assert "Cape" in result["title"]


async def test_config_flow_wma_requires_supply_plan(hass: HomeAssistant, rates) -> None:
    """Western Massachusetts R1 asks for Fixed vs Monthly Variable Basic Service."""
    from custom_components.eversource_rates.const import CONF_SUPPLY_PLAN

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "wma"}
    )
    assert result["step_id"] == "rate_class"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_RATE_CLASS: "r1"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "supply_plan"

    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SUPPLY_PLAN: "fixed"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TERRITORY: "wma",
        CONF_RATE_CLASS: "r1",
        CONF_SUPPLY_PLAN: "fixed",
    }
    assert result["result"].unique_id == "eversource_rates_wma_r1_fixed"
    assert "Western Massachusetts" in result["title"]
    assert "Fixed" in result["title"]


async def test_config_flow_supply_plan_maps_client_errors(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Supply-plan finalize maps connection failures to translated errors."""
    from custom_components.eversource_rates.api import EversourceConnectionError
    from custom_components.eversource_rates.const import CONF_SUPPLY_PLAN

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "wma"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_RATE_CLASS: "r1"}
    )
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(side_effect=EversourceConnectionError("down")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SUPPLY_PLAN: "monthly_variable"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_service_area_maps_client_errors(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Service-area finalize maps parse failures to translated errors."""
    from custom_components.eversource_rates.api import EversourceTariffParseError
    from custom_components.eversource_rates.const import (
        CONF_SERVICE_AREA,
        CONF_SUPPLY_PLAN,
    )
    from custom_components.eversource_rates.tariffs import (
        TARIFF_DEFINITIONS,
        TariffDefinition,
    )

    monkeypatch.setitem(
        TERRITORIES,
        "ema",
        Territory("ema", "Eastern Massachusetts", "ema", ("r1",)),
    )
    monkeypatch.setitem(
        TARIFF_DEFINITIONS,
        ("ema", "r1"),
        TariffDefinition(
            "ema",
            "r1",
            "R1 - Residential Non-Heating",
            supply_plans=("fixed",),
            service_areas=("main", "cape"),
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "ema"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_RATE_CLASS: "r1"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SUPPLY_PLAN: "fixed"}
    )
    assert result["step_id"] == "service_area"
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(side_effect=EversourceTariffParseError("bad")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERVICE_AREA: "main"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_tariff_data"}


async def test_config_flow_rejects_unsupported_rate_for_territory(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Posted rate classes outside supported_rate_classes are rejected."""
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.TERRITORIES",
        _synthetic_territories(),
    )
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.RATE_CLASS_NAMES",
        _synthetic_rate_names(),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "beta"}
    )
    assert result["step_id"] == "rate_class"
    rate_validator = next(iter(result["data_schema"].schema.values()))
    assert set(rate_validator.container) == {"r3"}

    with pytest.raises(InvalidData):
        # Schema validation rejects unsupported rate classes before the step body.
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RATE_CLASS: "r1"}
        )


async def test_config_flow_defensive_unsupported_inputs(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct step calls still reject unsupported territory/rate values."""
    from custom_components.eversource_rates.config_flow import (
        EversourceRatesConfigFlow,
    )

    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.TERRITORIES",
        _synthetic_territories(),
    )
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.RATE_CLASS_NAMES",
        _synthetic_rate_names(),
    )
    flow = EversourceRatesConfigFlow()
    flow.hass = hass

    bad_territory = await flow.async_step_user({CONF_TERRITORY: "missing"})
    assert bad_territory["type"] == FlowResultType.FORM
    assert bad_territory["errors"] == {"base": "unsupported_tariff"}

    flow._territory = "beta"
    bad_rate = await flow.async_step_rate_class({CONF_RATE_CLASS: "r1"})
    assert bad_rate["type"] == FlowResultType.FORM
    assert bad_rate["errors"] == {"base": "unsupported_tariff"}


async def test_config_flow_duplicate_entry_still_aborts(
    hass: HomeAssistant, rates
) -> None:
    """Duplicate territory/rate-class combinations still abort."""
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_TERRITORY: "nh"}
        )
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_RATE_CLASS: "r"}
        )
    assert first["type"] == FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_TERRITORY: "nh"}
    )
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {CONF_RATE_CLASS: "r"}
        )
    assert second["type"] == FlowResultType.ABORT
    assert second["reason"] == "already_configured"


async def test_config_flow_aborts_when_territory_has_no_rate_classes(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A territory with no recognized rate-class names aborts deliberately."""
    monkeypatch.setattr(
        "custom_components.eversource_rates.config_flow.TERRITORIES",
        {
            "nh": Territory("nh", "New Hampshire", "nh", ("r",)),
            "empty": Territory("empty", "Empty Territory", "empty", ("unknown",)),
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "empty"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unsupported_tariff"
