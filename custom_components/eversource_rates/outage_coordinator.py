"""Coordinator for polling public Eversource outage snapshots."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_OUTAGE_UPDATE_INTERVAL_MINUTES
from .outage_api import (
    EversourceOutageClient,
    EversourceOutageConnectionError,
    EversourceOutageParseError,
)
from .outage_models import EversourceOutageArea

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class EversourceOutageCoordinator(DataUpdateCoordinator[EversourceOutageArea]):
    """Manage polling for a single municipality's public outage snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EversourceOutageClient,
        *,
        territory: str,
        municipality: str,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the outage coordinator with 5-minute default cadence."""
        if update_interval is None:
            update_interval = timedelta(minutes=DEFAULT_OUTAGE_UPDATE_INTERVAL_MINUTES)
        super().__init__(
            hass,
            _LOGGER,
            name=f"Eversource Outage {territory.upper()} {municipality}",
            update_interval=update_interval,
        )
        self.client = client
        self.territory = territory
        self.municipality = municipality

    async def _async_update_data(self) -> EversourceOutageArea:
        """Fetch the latest outage snapshot for the configured municipality."""
        try:
            return await self.client.async_get_area(self.territory, self.municipality)
        except (EversourceOutageConnectionError, EversourceOutageParseError) as err:
            raise UpdateFailed(
                f"Error communicating with Eversource outage service: {err}"
            ) from err
