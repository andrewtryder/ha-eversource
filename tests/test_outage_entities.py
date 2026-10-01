"""Tests for Eversource outage entities (binary_sensor and sensor)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eversource_rates.const import (
    CONF_ENABLE_OUTAGE,
    CONF_OUTAGE_MUNICIPALITY,
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    DOMAIN,
)
from custom_components.eversource_rates.outage_api import (
    EversourceOutageConnectionError,
)
from custom_components.eversource_rates.outage_models import EversourceOutageArea


def _sample_area(
    customers_out: int = 12,
    customers_served: int = 19000,
    percent_out: float | None = 0.063,
) -> EversourceOutageArea:
    return EversourceOutageArea(
        territory="nh",
        area_name="CONCORD",
        customers_out=customers_out,
        customers_served=customers_served,
        percent_out=percent_out,
        source_url="https://outagemap.eversource.com/resources/data/external/interval_generation_data/test/report_hampshire.json",
        retrieved_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
    )


async def test_no_outage_configured_creates_no_outage_entities(
    hass: HomeAssistant, rates
) -> None:
    """Config entry with no outage configuration creates only tariff entities."""
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
    assert entry.runtime_data.outage_coordinator is None

    # Tariff sensor exists
    assert hass.states.get("sensor.eversource_total_electricity_rate") is not None
    # No outage binary sensor exists
    binary_sensors = [
        state.entity_id
        for state in hass.states.async_all("binary_sensor")
        if state.entity_id.startswith("binary_sensor.eversource")
    ]
    assert len(binary_sensors) == 0


async def test_outage_entities_created_with_problem_and_sensors(
    hass: HomeAssistant, rates
) -> None:
    """When configured, binary sensor and sensors are created.

    States and attributes are populated from the public outage snapshot.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_ENABLE_OUTAGE: True, CONF_OUTAGE_MUNICIPALITY: "CONCORD"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)

    sample = _sample_area(12, 19000, 0.063)
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(return_value=sample),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.outage_coordinator is not None

    # Binary sensor
    bs_state = hass.states.get("binary_sensor.eversource_nh_concord_outage")
    assert bs_state is not None
    assert bs_state.state == STATE_ON
    assert bs_state.attributes["device_class"] == "problem"
    assert bs_state.attributes["municipality"] == "CONCORD"
    assert bs_state.attributes["territory"] == "nh"
    assert bs_state.attributes["customers_out"] == 12
    assert bs_state.attributes["customers_served"] == 19000
    assert bs_state.attributes["percent_out"] == 0.063
    assert "report_hampshire.json" in bs_state.attributes["source_url"]

    # Sensors
    out_state = hass.states.get("sensor.eversource_nh_concord_customers_out")
    assert out_state is not None
    assert out_state.state == "12"
    assert out_state.attributes.get("unit_of_measurement") is None

    pct_state = hass.states.get("sensor.eversource_nh_concord_percent_out")
    assert pct_state is not None
    assert pct_state.state == "0.063"
    assert pct_state.attributes.get("unit_of_measurement") == "%"

    # Total served is diagnostic / disabled by default
    ent_reg = er.async_get(hass)
    served_entry = ent_reg.async_get("sensor.eversource_nh_concord_customers_served")
    assert served_entry is not None
    assert served_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Device registry check
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device_by_identifier(
        (DOMAIN, "nh_concord_outage"), entry.entry_id
    )
    assert device is not None
    assert device.name == "Eversource Concord Outage"
    assert device.manufacturer == "Eversource"
    assert device.model == "Outage reporting"
    assert (
        device.configuration_url
        == "https://outagemap.eversource.com/external/default.html"
    )


async def test_outage_binary_sensor_off_when_no_outages(
    hass: HomeAssistant, rates
) -> None:
    """When customers_out is 0, binary sensor is off."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_ENABLE_OUTAGE: True, CONF_OUTAGE_MUNICIPALITY: "MANCHESTER"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)

    sample = _sample_area(0, 45000, 0.0)
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(return_value=sample),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    bs_state = hass.states.get("binary_sensor.eversource_nh_manchester_outage")
    assert bs_state is not None
    assert bs_state.state == STATE_OFF


async def test_initial_outage_failure_does_not_break_tariff(
    hass: HomeAssistant, rates
) -> None:
    """If outage endpoint fails on startup, tariff entities still load normally."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_ENABLE_OUTAGE: True, CONF_OUTAGE_MUNICIPALITY: "CONCORD"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(side_effect=EversourceOutageConnectionError("Outage API down")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Entry is LOADED despite outage API failure
    assert entry.state is ConfigEntryState.LOADED
    # Tariff sensor is available and working
    assert hass.states.get("sensor.eversource_total_electricity_rate").state == str(
        rates.total_variable_rate
    )
    # Outage coordinator exists but has no data
    assert entry.runtime_data.outage_coordinator is not None
    assert entry.runtime_data.outage_coordinator.data is None

    # Outage entities are unavailable
    bs_state = hass.states.get("binary_sensor.eversource_nh_concord_outage")
    assert bs_state is not None
    assert bs_state.state == STATE_UNAVAILABLE


async def test_outage_entities_recovery_and_unload(hass: HomeAssistant, rates) -> None:
    """Test coordinator refresh, recovery, and clean unloading."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_ENABLE_OUTAGE: True, CONF_OUTAGE_MUNICIPALITY: "CONCORD"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)

    sample1 = _sample_area(12, 19000, 0.063)
    sample2 = _sample_area(0, 19000, 0.0)

    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(return_value=sample1),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.eversource_nh_concord_outage").state == STATE_ON
    )

    # Next update has 0 outages
    with patch(
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
        AsyncMock(return_value=sample2),
    ):
        await entry.runtime_data.outage_coordinator.async_refresh()
        await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.eversource_nh_concord_outage").state == STATE_OFF
    )
    assert hass.states.get("sensor.eversource_nh_concord_customers_out").state == "0"

    # Unload entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
