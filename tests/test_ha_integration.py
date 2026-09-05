"""Home Assistant integration-layer tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
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
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    TERRITORIES,
    Territory,
)
from custom_components.eversource_rates.coordinator import EversourceRatesCoordinator


def _coordinator(hass, client) -> EversourceRatesCoordinator:
    return EversourceRatesCoordinator(
        hass,
        client,
        update_interval=timedelta(hours=DEFAULT_UPDATE_INTERVAL_HOURS),
    )


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
    registry = er.async_get(hass)
    assert (
        registry.async_get("sensor.eversource_total_electricity_rate").unique_id
        == "eversource_rates_nh_r_total_electricity_rate"
    )

    for entity_id in (
        "sensor.eversource_supply_rate",
        "sensor.eversource_delivery_rate",
        "sensor.eversource_total_electricity_rate",
        "sensor.eversource_customer_charge",
    ):
        _assert_rate_sensor_metadata(hass, entity_id)


async def test_setup_wma_uses_supply_plan_prefixed_entity_ids(
    hass: HomeAssistant, rates
) -> None:
    """WMA Fixed entries include supply_plan in object and unique IDs."""
    from dataclasses import replace

    from custom_components.eversource_rates.const import CONF_SUPPLY_PLAN

    wma_rates = replace(rates, territory="wma", rate_class="r1", supply_plan="fixed")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TERRITORY: "wma",
            CONF_RATE_CLASS: "r1",
            CONF_SUPPLY_PLAN: "fixed",
        },
        unique_id="eversource_rates_wma_r1_fixed",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=wma_rates),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    total = hass.states.get("sensor.eversource_wma_r1_fixed_total_electricity_rate")
    assert total is not None
    assert total.attributes["supply_plan"] == "fixed"
    registry = er.async_get(hass)
    assert (
        registry.async_get(
            "sensor.eversource_wma_r1_fixed_total_electricity_rate"
        ).unique_id
        == "eversource_rates_wma_r1_fixed_total_electricity_rate"
    )


async def test_setup_ema_includes_service_area_in_device_and_entity_ids(
    hass: HomeAssistant, rates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Service-area selections appear in entity object IDs and device names."""
    from dataclasses import replace

    from custom_components.eversource_rates.const import (
        CONF_SERVICE_AREA,
        CONF_SUPPLY_PLAN,
    )

    monkeypatch.setitem(
        TERRITORIES,
        "ema",
        Territory("ema", "Eastern Massachusetts", "ema", ("r1",)),
    )
    ema_rates = replace(
        rates,
        territory="ema",
        rate_class="r1",
        supply_plan="fixed",
        service_area="cape",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TERRITORY: "ema",
            CONF_RATE_CLASS: "r1",
            CONF_SUPPLY_PLAN: "fixed",
            CONF_SERVICE_AREA: "cape",
        },
        unique_id="eversource_rates_ema_r1_fixed_cape",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.eversource_rates.EversourceClient.async_get_rates",
        AsyncMock(return_value=ema_rates),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entity_id = "sensor.eversource_ema_r1_fixed_cape_total_electricity_rate"
    total = hass.states.get(entity_id)
    assert total is not None
    assert total.attributes["service_area"] == "cape"


async def test_setup_can_enable_diagnostic_component_sensor(
    hass: HomeAssistant, rates
) -> None:
    """Disabled delivery-component sensors can be enabled after setup."""
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


async def test_setup_constructs_client_with_selection(
    hass: HomeAssistant, rates
) -> None:
    """Client identity is a TariffSelection; TariffSource owns cookies/URLs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TERRITORY: "nh", CONF_RATE_CLASS: "r"},
        unique_id="eversource_rates_nh_r",
    )
    entry.add_to_hass(hass)
    with patch("custom_components.eversource_rates.EversourceClient") as client:
        client.return_value.async_get_rates = AsyncMock(return_value=rates)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    selection = client.call_args.kwargs["selection"]
    assert selection.territory == "nh"
    assert selection.rate_class == "r"
    assert selection.supply_plan is None


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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "nh"}
    )
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RATE_CLASS: "r"}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": error}


async def test_config_flow_creates_unique_entry(hass: HomeAssistant, rates) -> None:
    """Validate tariff access before creating a uniquely identified entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TERRITORY: "nh"}
    )
    with patch(
        "custom_components.eversource_rates.config_flow.EversourceClient.async_get_rates",
        AsyncMock(return_value=rates),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RATE_CLASS: "r"}
        )
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "eversource_rates_nh_r"


async def test_coordinator_converts_client_error_to_update_failed(
    hass: HomeAssistant,
) -> None:
    """Preserve normal coordinator failure semantics for a remote outage."""
    client = AsyncMock()
    client.async_get_rates.side_effect = EversourceConnectionError("offline")
    coordinator = _coordinator(hass, client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_refreshes_when_only_retrieved_at_changes(
    hass: HomeAssistant, rates
) -> None:
    """Identical tariff values with a newer retrieved_at still update listeners."""
    from copy import replace
    from datetime import UTC, datetime, timedelta

    first = rates
    second = replace(rates, retrieved_at=datetime(2026, 9, 6, tzinfo=UTC))
    assert first.total_variable_rate == second.total_variable_rate
    assert first != second

    client = AsyncMock()
    client.async_get_rates.side_effect = [first, second]
    coordinator = _coordinator(hass, client)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data.retrieved_at == first.retrieved_at

    notifications: list[datetime] = []

    def _listener() -> None:
        notifications.append(coordinator.data.retrieved_at)

    unsub = coordinator.async_add_listener(_listener)
    await coordinator.async_refresh()
    unsub()

    assert coordinator.last_update_success is True
    assert coordinator.data.total_variable_rate == first.total_variable_rate
    assert coordinator.data.retrieved_at == second.retrieved_at
    assert notifications == [second.retrieved_at]
    assert second.retrieved_at - first.retrieved_at == timedelta(days=1)


async def test_diagnostic_rider_survives_disappear_and_reappear(
    hass: HomeAssistant, rates
) -> None:
    """A diagnostic rider stays available→unavailable→available without errors."""
    from copy import replace

    from custom_components.eversource_rates.models import (
        DeliveryComponent,
        DeliveryRates,
    )
    from custom_components.eversource_rates.sensor import EversourceComponentSensor

    components = dict(rates.delivery.variable_components)
    components["temporary_reliability_rider"] = DeliveryComponent(
        "temporary_reliability_rider",
        "Temporary Reliability Rider",
        Decimal("0.001"),
    )
    rates_with_rider = replace(
        rates,
        delivery=DeliveryRates(rates.delivery.customer_charge, components),
    )

    client = AsyncMock()
    client.async_get_rates = AsyncMock(return_value=rates_with_rider)
    coordinator = _coordinator(hass, client)
    await coordinator.async_refresh()

    sensor = EversourceComponentSensor(
        coordinator,
        "temporary_reliability_rider",
        "Eversource Temporary Reliability Rider",
    )
    sensor.hass = hass
    sensor.entity_id = "sensor.eversource_temporary_reliability_rider"

    assert sensor.available is True
    assert sensor.native_value == Decimal("0.001")

    client.async_get_rates = AsyncMock(return_value=rates)
    await coordinator.async_refresh()
    assert sensor.available is False
    assert sensor.native_value is None

    client.async_get_rates = AsyncMock(return_value=rates_with_rider)
    await coordinator.async_refresh()
    assert sensor.available is True
    assert sensor.native_value == Decimal("0.001")
