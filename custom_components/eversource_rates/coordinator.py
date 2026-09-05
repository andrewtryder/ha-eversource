"""Coordinator for periodic tariff retrieval."""

from __future__ import annotations

import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EversourceClient, EversourceError
from .const import DOMAIN, UPDATE_INTERVAL
from .models import EversourceRates

_LOGGER = logging.getLogger(__name__)


class EversourceRatesCoordinator(DataUpdateCoordinator[EversourceRates]):
    """Poll tariffs while retaining coordinator data on a failed refresh."""

    def __init__(self, hass, client: EversourceClient) -> None:
        """Initialize the periodic Home Assistant coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> EversourceRates:
        try:
            return await self.client.async_get_rates()
        except EversourceError as err:
            raise UpdateFailed(str(err)) from err
