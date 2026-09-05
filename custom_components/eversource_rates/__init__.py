"""Eversource Rates integration setup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .api import EversourceClient
from .const import CONF_RATE_CLASS, CONF_TERRITORY

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class EversourceRuntimeData:
    """Runtime objects associated with one config entry."""

    coordinator: Any


EversourceConfigEntry = Any


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[EversourceRuntimeData]
) -> bool:
    """Set up Eversource Rates from a config entry."""
    from homeassistant.const import Platform
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .coordinator import EversourceRatesCoordinator

    client = EversourceClient(
        async_get_clientsession(hass),
        entry.data[CONF_TERRITORY],
        entry.data[CONF_RATE_CLASS],
    )
    coordinator = EversourceRatesCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = EversourceRuntimeData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[EversourceRuntimeData]
) -> bool:
    """Unload an Eversource config entry."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))
