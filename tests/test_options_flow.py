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
    CONF_ENABLE_OUTAGE,
    CONF_OUTAGE_MUNICIPALITY,
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    update_interval_hours_from_options,
    update_interval_timedelta_from_options,
)
from custom_components.eversource_rates.outage_api import (
    EversourceOutageConnectionError,
    EversourceOutageParseError,
)
from custom_components.eversource_rates.outage_models import EversourceOutageArea


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


def _mock_outage_areas() -> dict[str, EversourceOutageArea]:
    from datetime import UTC, datetime

    return {
        "CONCORD": EversourceOutageArea(
            territory="nh",
            area_name="CONCORD",
            customers_out=12,
            customers_served=19000,
            percent_out=0.063,
            source_url="https://example.com/report.json",
            retrieved_at=datetime.now(UTC),
        ),
        "MANCHESTER": EversourceOutageArea(
            territory="nh",
            area_name="MANCHESTER",
            customers_out=0,
            customers_served=45000,
            percent_out=0.0,
            source_url="https://example.com/report.json",
            retrieved_at=datetime.now(UTC),
        ),
    }


async def test_options_flow_enable_outage_monitoring(
    hass: HomeAssistant, rates
) -> None:
    """Enabling outage monitoring prompts for municipality selection.

    It saves both update interval and selected municipality options.
    """
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
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
        AsyncMock(return_value=_mock_outage_areas()),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 12, CONF_ENABLE_OUTAGE: True},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "outage"

    mock_sample = _mock_outage_areas()["CONCORD"]
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(return_value=mock_sample),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
            AsyncMock(return_value=_mock_outage_areas()),
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_OUTAGE_MUNICIPALITY: "CONCORD"},
        )

        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL_HOURS] == 12
    assert entry.options[CONF_OUTAGE_MUNICIPALITY] == "CONCORD"
    assert entry.runtime_data.outage_coordinator is not None
    assert entry.runtime_data.outage_coordinator.data.customers_out == 12


async def test_options_flow_disable_outage_monitoring(
    hass: HomeAssistant, rates
) -> None:
    """Disabling outage monitoring removes municipality from options and coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_UPDATE_INTERVAL_HOURS: 12, CONF_OUTAGE_MUNICIPALITY: "CONCORD"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)
    mock_sample = _mock_outage_areas()["CONCORD"]
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_get_area",
            AsyncMock(return_value=mock_sample),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.outage_coordinator is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 24, CONF_ENABLE_OUTAGE: False},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_OUTAGE_MUNICIPALITY not in entry.options
    assert entry.options[CONF_UPDATE_INTERVAL_HOURS] == 24
    assert entry.runtime_data.outage_coordinator is None


async def test_options_flow_outage_connection_error(hass: HomeAssistant, rates) -> None:
    """Connection error when listing areas surfaces cannot_connect error."""
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
    with patch(
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
        AsyncMock(side_effect=EversourceOutageConnectionError("Connection lost")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 24, CONF_ENABLE_OUTAGE: True},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "outage"
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_outage_parse_error(hass: HomeAssistant, rates) -> None:
    """Parse error when listing areas surfaces invalid_outage_data error."""
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
    with patch(
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
        AsyncMock(side_effect=EversourceOutageParseError("Malformed data")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 24, CONF_ENABLE_OUTAGE: True},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "outage"
    assert result["errors"]["base"] == "invalid_outage_data"


async def test_options_flow_outage_discovery_failure_cannot_be_bypassed(
    hass: HomeAssistant, rates
) -> None:
    """Discovery failure cannot be bypassed by submitting an arbitrary municipality.

    1. Fetch fails
    2. Form displays error
    3. User submits arbitrary municipality
    4. Options are NOT saved
    """
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

    # Step 1 & 2: Fetch fails -> form displays error
    with patch(
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
        AsyncMock(side_effect=EversourceOutageConnectionError("Connection lost")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_UPDATE_INTERVAL_HOURS: 24, CONF_ENABLE_OUTAGE: True},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "outage"
    assert result["errors"]["base"] == "cannot_connect"

    # Step 3 & 4: User submits arbitrary municipality while discovery fails -> NOT saved
    with patch(
        "custom_components.eversource_rates.outage_api.EversourceOutageClient.async_list_areas",
        AsyncMock(side_effect=EversourceOutageConnectionError("Connection lost")),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_OUTAGE_MUNICIPALITY: "ARBITRARY_CITY"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "outage"
    assert result["errors"]["base"] == "cannot_connect"
    assert CONF_OUTAGE_MUNICIPALITY not in entry.options
