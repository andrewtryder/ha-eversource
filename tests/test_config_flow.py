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
