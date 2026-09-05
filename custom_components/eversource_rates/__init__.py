"""Eversource Rates integration setup."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import EversourceClient
from .const import CONF_RATE_CLASS, CONF_TERRITORY, TERRITORIES
from .coordinator import EversourceRatesCoordinator


@dataclass(slots=True)
class EversourceRuntimeData:
    """Runtime objects associated with one config entry."""

    coordinator: EversourceRatesCoordinator


type EversourceConfigEntry = ConfigEntry[EversourceRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EversourceConfigEntry) -> bool:
    """Set up Eversource Rates from a config entry."""
    from homeassistant.const import Platform
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    territory = TERRITORIES[entry.data[CONF_TERRITORY]]
    client = EversourceClient(
        async_get_clientsession(hass),
        territory.segment,
        entry.data[CONF_RATE_CLASS],
    )
    coordinator = EversourceRatesCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = EversourceRuntimeData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EversourceConfigEntry) -> bool:
    """Unload an Eversource config entry."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))
