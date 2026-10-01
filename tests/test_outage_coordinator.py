"""Tests for the Eversource outage coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from custom_components.eversource_rates.outage_api import (
    EversourceOutageClient,
    EversourceOutageConnectionError,
    EversourceOutageParseError,
)
from custom_components.eversource_rates.outage_coordinator import (
    EversourceOutageCoordinator,
)
from custom_components.eversource_rates.outage_models import EversourceOutageArea


def _make_sample_area(
    customers_out: int = 12, customers_served: int = 19000
) -> EversourceOutageArea:
    return EversourceOutageArea(
        territory="nh",
        area_name="CONCORD",
        customers_out=customers_out,
        customers_served=customers_served,
        percent_out=round(customers_out / customers_served * 100, 3)
        if customers_served
        else 0.0,
        source_url="https://outagemap.eversource.com/resources/data/external/interval_generation_data/test/report_hampshire.json",
        retrieved_at=datetime.now(UTC),
    )


async def test_coordinator_successful_refresh(hass: HomeAssistant) -> None:
    """Coordinator successfully retrieves and stores outage snapshot."""
    client = EversourceOutageClient(AsyncMock())
    sample = _make_sample_area(12, 19000)

    with patch.object(client, "async_get_area", AsyncMock(return_value=sample)):
        coordinator = EversourceOutageCoordinator(
            hass, client=client, territory="nh", municipality="CONCORD"
        )
        await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == sample
    assert coordinator.data.customers_out == 12
    assert coordinator.data.area_name == "CONCORD"
    assert coordinator.update_interval == timedelta(minutes=5)


async def test_coordinator_connection_error_raises_update_failed_and_preserves_data(
    hass: HomeAssistant,
) -> None:
    """Connection errors raise UpdateFailed and coordinator keeps previous data."""
    client = EversourceOutageClient(AsyncMock())
    sample = _make_sample_area(12, 19000)

    with patch.object(client, "async_get_area", AsyncMock(return_value=sample)):
        coordinator = EversourceOutageCoordinator(
            hass, client=client, territory="nh", municipality="CONCORD"
        )
        await coordinator.async_refresh()

    assert coordinator.data == sample

    with patch.object(
        client,
        "async_get_area",
        AsyncMock(side_effect=EversourceOutageConnectionError("Connection lost")),
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    # Data is preserved from prior successful update
    assert coordinator.data == sample


async def test_coordinator_parse_error_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """Parse errors raise UpdateFailed."""
    client = EversourceOutageClient(AsyncMock())

    with patch.object(
        client,
        "async_get_area",
        AsyncMock(side_effect=EversourceOutageParseError("Malformed upstream JSON")),
    ):
        coordinator = EversourceOutageCoordinator(
            hass, client=client, territory="nh", municipality="CONCORD"
        )
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.data is None


async def test_coordinator_recovery(hass: HomeAssistant) -> None:
    """Coordinator recovers after a temporary failure."""
    client = EversourceOutageClient(AsyncMock())
    sample1 = _make_sample_area(12, 19000)
    sample2 = _make_sample_area(0, 19000)

    # Initial success
    with patch.object(client, "async_get_area", AsyncMock(return_value=sample1)):
        coordinator = EversourceOutageCoordinator(
            hass, client=client, territory="nh", municipality="CONCORD"
        )
        await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data.customers_out == 12

    # Temporary failure
    with patch.object(
        client,
        "async_get_area",
        AsyncMock(side_effect=EversourceOutageConnectionError("Network error")),
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.data.customers_out == 12

    # Recovery
    with patch.object(client, "async_get_area", AsyncMock(return_value=sample2)):
        await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data.customers_out == 0
