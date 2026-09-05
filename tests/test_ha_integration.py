"""Home Assistant integration-layer tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eversource_rates.api import (
    EversourceConnectionError,
    EversourceTariffParseError,
    EversourceUnsupportedTariffError,
)
from custom_components.eversource_rates.const import (
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    DOMAIN,
    Territory,
)
from custom_components.eversource_rates.coordinator import EversourceRatesCoordinator


def _assert_rate_sensor_metadata(hass: HomeAssistant, entity_id: str) -> None:
    """Rate sensors use measurement state class without a monetary device class."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["state_class"] == "measurement"
    assert "device_class" not in state.attributes


async def test_setup_creates_primary_and_diagnostic_sensors(
    hass: HomeAssistant, rates
) -> None:
    """Set up the entry and expose correct tariff states and metadata."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    total = hass.states.get("sensor.eversource_total_electricity_rate")
    assert total.state == "0.25918"
    assert total.attributes["unit_of_measurement"] == "USD/kWh"
    assert total.attributes["supply_effective_date"] == "2026-08-01"
    assert hass.states.get("sensor.eversource_customer_charge").state == "19.81"
    assert hass.states.get("sensor.eversource_distribution_charge") is None

    for entity_id in (
        "sensor.eversource_supply_rate",
        "sensor.eversource_delivery_rate",
        "sensor.eversource_total_electricity_rate",
        "sensor.eversource_customer_charge",
    ):
        _assert_rate_sensor_metadata(hass, entity_id)

    registry = er.async_get(hass)
    registry.async_update_entity(
        "sensor.eversource_distribution_charge", disabled_by=None
    )
    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    distribution = hass.states.get("sensor.eversource_distribution_charge")
    assert distribution is not None
    assert distribution.state == "0.06727"
    _assert_rate_sensor_metadata(hass, "sensor.eversource_distribution_charge")


async def test_setup_uses_territory_sitefinity_segment(
    hass: HomeAssistant, rates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the territory's Sitefinity segment rather than its config key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(
        "custom_components.eversource_rates.TERRITORIES",
        {"nh": Territory("nh", "New Hampshire", "sitefinity-nh", ("r",))},
    )
    with patch("custom_components.eversource_rates.EversourceClient") as client:
        client.return_value.async_get_rates = AsyncMock(return_value=rates)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert client.call_args.args[1:] == ("sitefinity-nh", "r")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EversourceConnectionError("down"), "cannot_connect"),
        (EversourceTariffParseError("bad"), "invalid_tariff_data"),
        (EversourceUnsupportedTariffError("no"), "unsupported_tariff"),
    ],
)
async def test_config_flow_displays_client_errors(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Map public-client failures to translated config-flow errors."""
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": error}


async def test_config_flow_creates_unique_entry(hass: HomeAssistant, rates) -> None:
    """Validate tariff access before creating a uniquely identified entry."""
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        )
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "eversource_rates_nh_r"


async def test_coordinator_converts_client_error_to_update_failed(
    hass: HomeAssistant,
) -> None:
    """Preserve normal coordinator failure semantics for a remote outage."""
    client = AsyncMock()
    client.async_get_rates.side_effect = EversourceConnectionError("offline")
    coordinator = EversourceRatesCoordinator(hass, client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
