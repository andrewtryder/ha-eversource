"""Device Activity events for rate refreshes and municipality outage polls."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eversource_rates.api import EversourceConnectionError
from custom_components.eversource_rates.const import (
    CONF_OUTAGE_MUNICIPALITY,
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    DOMAIN,
)
from custom_components.eversource_rates.models import DeliveryRates
from custom_components.eversource_rates.outage_api import (
    EversourceOutageConnectionError,
)
from custom_components.eversource_rates.outage_models import EversourceOutageArea


def _entry(*, municipality: str | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        options={CONF_OUTAGE_MUNICIPALITY: municipality} if municipality else {},
        unique_id="eversource_rates_nh_r",
    )


def _area(count: int) -> EversourceOutageArea:
    return EversourceOutageArea(
        territory="nh",
        area_name="CONCORD",
        customers_out=count,
        customers_served=19000,
        percent_out=round(count / 19000 * 100, 3),
        source_url="https://example.test/outages",
        retrieved_at=datetime(2026, 11, 13, tzinfo=UTC),
    )


async def test_rate_activity_tracks_unchanged_changed_failure_and_recovery(
    hass: HomeAssistant, rates
) -> None:
    """A native event is emitted for every successful rate poll."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ) as get_rates:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        event_id = registry.async_get_entity_id(
            "event", DOMAIN, "eversource_rates_nh_r_rate_activity"
        )
        assert event_id is not None
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "rates_checked"
        assert state.attributes["total_rate_usd_per_kwh"] == str(
            rates.total_variable_rate
        )
        assert state.attributes["message"] == (
            "Initial Eversource rates check succeeded"
        )
        assert registry.async_get(event_id).device_id == registry.async_get(
            "sensor.eversource_total_electricity_rate"
        ).device_id

        # A successful poll is visible even when tariff values are unchanged.
        first_timestamp = state.state
        await entry.runtime_data.coordinator.async_refresh()
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "rates_checked"
        assert state.state != first_timestamp

        # Supply change.
        new_rates = replace(
            rates, supply=replace(rates.supply, rate=Decimal("0.15009"))
        )
        get_rates.return_value = new_rates
        await entry.runtime_data.coordinator.async_refresh()
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "rates_changed"
        assert state.attributes["previous_total_rate_usd_per_kwh"] == str(
            rates.total_variable_rate
        )

        # Fixed charge changes are separately recognized.
        charge_rates = replace(
            new_rates,
            delivery=DeliveryRates(
                Decimal("20.12"), new_rates.delivery.variable_components
            ),
        )
        get_rates.return_value = charge_rates
        await entry.runtime_data.coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == "rates_changed"

        # Delivery variable changes are recognized even if supply is unchanged.
        components = dict(charge_rates.delivery.variable_components)
        component = components["distribution_charge"]
        components["distribution_charge"] = replace(
            component, rate=component.rate + Decimal("0.001")
        )
        delivery_rates = replace(
            charge_rates,
            delivery=DeliveryRates(charge_rates.delivery.customer_charge, components),
        )
        get_rates.return_value = delivery_rates
        await entry.runtime_data.coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == "rates_changed"

        get_rates.side_effect = EversourceConnectionError("temporarily down")
        await entry.runtime_data.coordinator.async_refresh()
        failed = hass.states.get(event_id)
        assert failed.attributes["event_type"] == "rate_check_failed"
        assert "temporarily down" in failed.attributes["error"]

        # Repeated failures do not flood Activity until state changes.
        await entry.runtime_data.coordinator.async_refresh()
        assert hass.states.get(event_id).state == failed.state

        get_rates.side_effect = None
        get_rates.return_value = delivery_rates
        await entry.runtime_data.coordinator.async_refresh()
        recovered = hass.states.get(event_id)
        assert recovered.attributes["event_type"] == "rate_check_recovered"

        await entry.runtime_data.coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == "rates_checked"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(event_id) is None


async def test_outage_activity_records_checks_changes_and_failures(
    hass: HomeAssistant, rates
) -> None:
    """Even all-clear five-minute polls create device Activity events."""
    entry = _entry(municipality="CONCORD")
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api."
            "EversourceOutageClient.async_get_area",
            AsyncMock(return_value=_area(0)),
        ) as get_area,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        event_id = registry.async_get_entity_id(
            "event", DOMAIN, "eversource_rates_nh_r_outage_activity"
        )
        assert event_id is not None
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "outage_checked"
        assert state.attributes["customers_out"] == 0
        assert registry.async_get(event_id).device_id == registry.async_get(
            "binary_sensor.eversource_concord_outage"
        ).device_id

        first_timestamp = state.state
        await entry.runtime_data.outage_coordinator.async_refresh()
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "outage_checked"
        assert state.state != first_timestamp

        get_area.return_value = _area(12)
        await entry.runtime_data.outage_coordinator.async_refresh()
        state = hass.states.get(event_id)
        assert state.attributes["event_type"] == "outage_detected"
        assert state.attributes["previous_customers_out"] == 0

        get_area.return_value = _area(6)
        await entry.runtime_data.outage_coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == (
            "outage_count_changed"
        )

        get_area.return_value = _area(0)
        await entry.runtime_data.outage_coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == "outage_cleared"

        get_area.side_effect = EversourceOutageConnectionError("API offline")
        await entry.runtime_data.outage_coordinator.async_refresh()
        failed = hass.states.get(event_id)
        assert failed.attributes["event_type"] == "outage_check_failed"
        assert "API offline" in failed.attributes["error"]

        await entry.runtime_data.outage_coordinator.async_refresh()
        assert hass.states.get(event_id).state == failed.state

        get_area.side_effect = None
        get_area.return_value = _area(0)
        await entry.runtime_data.outage_coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == (
            "outage_check_recovered"
        )
        await entry.runtime_data.outage_coordinator.async_refresh()
        assert hass.states.get(event_id).attributes["event_type"] == "outage_checked"


async def test_initial_outage_failure_is_visible_in_activity(
    hass: HomeAssistant, rates
) -> None:
    """Activity still reports an unavailable outage feed on startup."""
    entry = _entry(municipality="CONCORD")
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.eversource_rates.EversourceClient.async_get_rates",
            AsyncMock(return_value=rates),
        ),
        patch(
            "custom_components.eversource_rates.outage_api."
            "EversourceOutageClient.async_get_area",
            AsyncMock(side_effect=EversourceOutageConnectionError("unavailable")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    event_id = registry.async_get_entity_id(
        "event", DOMAIN, "eversource_rates_nh_r_outage_activity"
    )
    assert event_id is not None
    state = hass.states.get(event_id)
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["event_type"] == "outage_check_failed"
    assert state.attributes["municipality"] == "CONCORD"
