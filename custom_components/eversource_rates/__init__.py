"""Eversource Rates integration setup."""

from __future__ import annotations

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError as err:  # pragma: no cover - developer tooling without HA
    # Allow importing parser/api modules from tools/ without Home Assistant installed.
    # Only suppress the missing Home Assistant package itself — re-raise anything else.
    missing = err.name or ""
    if missing != "homeassistant" and not missing.startswith("homeassistant."):
        raise
else:
    import logging
    from dataclasses import dataclass

    from .api import EversourceClient
    from .const import (
        CONF_OUTAGE_MUNICIPALITY,
        CONF_TERRITORY,
        update_interval_timedelta_from_options,
    )
    from .coordinator import EversourceRatesCoordinator
    from .outage_api import EversourceOutageClient
    from .outage_coordinator import EversourceOutageCoordinator

    _LOGGER = logging.getLogger(__name__)

    @dataclass(slots=True)
    class EversourceRuntimeData:
        """Runtime objects associated with one config entry."""

        coordinator: EversourceRatesCoordinator
        outage_coordinator: EversourceOutageCoordinator | None = None

    type EversourceConfigEntry = ConfigEntry[EversourceRuntimeData]

    PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR, Platform.BINARY_SENSOR)

    async def async_setup_entry(
        hass: HomeAssistant, entry: EversourceConfigEntry
    ) -> bool:
        """Set up Eversource Rates from a config entry."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        from .tariffs import selection_from_entry_data

        session = async_get_clientsession(hass)
        client = EversourceClient(
            session,
            selection=selection_from_entry_data(dict(entry.data)),
        )
        coordinator = EversourceRatesCoordinator(
            hass,
            client,
            update_interval=update_interval_timedelta_from_options(dict(entry.options)),
        )
        await coordinator.async_config_entry_first_refresh()

        outage_municipality = entry.options.get(CONF_OUTAGE_MUNICIPALITY)
        outage_coordinator: EversourceOutageCoordinator | None = None
        if outage_municipality:
            outage_client = EversourceOutageClient(session)
            outage_coordinator = EversourceOutageCoordinator(
                hass,
                outage_client,
                territory=entry.data[CONF_TERRITORY],
                municipality=outage_municipality,
            )
            # Use async_refresh() so an initial outage API failure logs a warning and
            # marks the coordinator unsuccessful without raising ConfigEntryNotReady
            # or catching broad programming exceptions.
            await outage_coordinator.async_refresh()

        entry.runtime_data = EversourceRuntimeData(
            coordinator=coordinator,
            outage_coordinator=outage_coordinator,
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    async def async_unload_entry(
        hass: HomeAssistant, entry: EversourceConfigEntry
    ) -> bool:
        """Unload an Eversource config entry."""
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
