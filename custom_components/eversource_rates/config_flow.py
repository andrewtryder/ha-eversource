"""Config flow for verified Eversource tariffs."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EversourceClient,
    EversourceConnectionError,
    EversourceTariffParseError,
    EversourceUnsupportedTariffError,
)
from .const import (
    CONF_RATE_CLASS,
    CONF_TERRITORY,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    RATE_CLASS_NAMES,
    TERRITORIES,
    update_interval_hours_from_options,
    update_interval_options,
)


def _territory_options() -> dict[str, str]:
    return {key: item.name for key, item in TERRITORIES.items()}


def _rate_class_options(territory_key: str) -> dict[str, str]:
    territory = TERRITORIES[territory_key]
    return {
        rate_class: RATE_CLASS_NAMES[rate_class]
        for rate_class in territory.supported_rate_classes
        if rate_class in RATE_CLASS_NAMES
    }


class EversourceRatesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a known, public Eversource tariff without user credentials."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize transient multi-step selection state."""
        self._territory: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow (reload-on-save; no update listener)."""
        return EversourceRatesOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Select the service territory first."""
        errors: dict[str, str] = {}
        if user_input is not None:
            territory = user_input[CONF_TERRITORY]
            if territory not in TERRITORIES:
                errors["base"] = "unsupported_tariff"
            else:
                self._territory = territory
                return await self.async_step_rate_class()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TERRITORY, default="nh"): vol.In(
                        _territory_options()
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_rate_class(self, user_input=None):
        """Select a rate class supported by the chosen territory."""
        assert self._territory is not None
        options = _rate_class_options(self._territory)
        if not options:
            # Malformed territory definition with no named rate classes.
            return self.async_abort(reason="unsupported_tariff")
        errors: dict[str, str] = {}
        if user_input is not None:
            rate_class = user_input[CONF_RATE_CLASS]
            if rate_class not in options:
                errors["base"] = "unsupported_tariff"
            else:
                await self.async_set_unique_id(
                    f"{DOMAIN}_{self._territory}_{rate_class}"
                )
                self._abort_if_unique_id_configured()
                try:
                    await EversourceClient(
                        async_get_clientsession(self.hass),
                        territory=TERRITORIES[self._territory].key,
                        segment=TERRITORIES[self._territory].segment,
                        rate_class=rate_class,
                    ).async_get_rates()
                except EversourceConnectionError:
                    errors["base"] = "cannot_connect"
                except EversourceTariffParseError:
                    errors["base"] = "invalid_tariff_data"
                except EversourceUnsupportedTariffError:
                    errors["base"] = "unsupported_tariff"
                else:
                    title = (
                        f"Eversource {TERRITORIES[self._territory].name} "
                        f"{RATE_CLASS_NAMES[rate_class]}"
                    )
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_TERRITORY: self._territory,
                            CONF_RATE_CLASS: rate_class,
                        },
                    )

        default_rate = next(iter(options))
        return self.async_show_form(
            step_id="rate_class",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RATE_CLASS, default=default_rate): vol.In(
                        options
                    ),
                }
            ),
            errors=errors,
        )


class EversourceRatesOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure tariff polling interval; saving reloads the config entry."""

    async def async_step_init(self, user_input=None):
        """Manage the tariff update interval option."""
        if user_input is not None:
            hours = int(user_input[CONF_UPDATE_INTERVAL_HOURS])
            return self.async_create_entry(
                title="",
                data={CONF_UPDATE_INTERVAL_HOURS: hours},
            )

        current = update_interval_hours_from_options(dict(self.config_entry.options))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL_HOURS,
                        default=current or DEFAULT_UPDATE_INTERVAL_HOURS,
                    ): vol.In(update_interval_options()),
                }
            ),
        )
