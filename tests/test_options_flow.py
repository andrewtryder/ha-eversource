"""Options-flow and update-interval resolution tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eversource_rates.const import (
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    update_interval_hours_from_options,
    update_interval_timedelta_from_options,
)


def test_default_update_interval_is_24_hours() -> None:
    """Default constant and empty options both resolve to 24 hours."""
    assert DEFAULT_UPDATE_INTERVAL_HOURS == 24
    assert update_interval_hours_from_options(None) == 24
    assert update_interval_hours_from_options({}) == 24
    assert update_interval_timedelta_from_options({}) == timedelta(hours=24)


def test_update_interval_rejects_invalid_stored_values() -> None:
    """Malformed or unsupported stored options fall back to the default."""
    assert update_interval_hours_from_options({CONF_UPDATE_INTERVAL_HOURS: 5}) == 24
    assert (
        update_interval_hours_from_options({CONF_UPDATE_INTERVAL_HOURS: "nope"}) == 24
    )
    assert update_interval_hours_from_options({CONF_UPDATE_INTERVAL_HOURS: 6}) == 6
    assert update_interval_hours_from_options({CONF_UPDATE_INTERVAL_HOURS: 168}) == 168


async def test_setup_without_options_uses_24_hour_interval(
    hass: HomeAssistant, rates
) -> None:
    """Existing entries with no options transparently use the 24-hour default."""
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
    assert entry.runtime_data.coordinator.update_interval == timedelta(hours=24)


@pytest.mark.parametrize("hours", [6, 48, 168])
async def test_options_flow_sets_interval_and_reloads(
    hass: HomeAssistant, rates, hours: int
) -> None:
    """Saving an interval option reloads the entry with that coordinator interval."""
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

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: hours},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL_HOURS] == hours
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.update_interval == timedelta(hours=hours)
    assert hass.states.get("sensor.eversource_total_electricity_rate").state == str(
        rates.total_variable_rate
    )


async def test_options_flow_rejects_invalid_interval(
    hass: HomeAssistant, rates
) -> None:
    """Schema validation rejects values outside the fixed select."""
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

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 5},
        )
