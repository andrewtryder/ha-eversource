"""Config flow for verified Eversource tariffs."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
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
    DOMAIN,
    RATE_CLASS_NAMES,
    TERRITORIES,
)


class EversourceRatesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a known, public Eversource tariff without user credentials."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle tariff selection and verify public retrieval."""
        errors = {}
        if user_input is not None:
            territory = user_input[CONF_TERRITORY]
            rate_class = user_input[CONF_RATE_CLASS]
            await self.async_set_unique_id(f"{DOMAIN}_{territory}_{rate_class}")
            self._abort_if_unique_id_configured()
            try:
                await EversourceClient(
                    async_get_clientsession(self.hass),
                    territory=TERRITORIES[territory].key,
                    segment=TERRITORIES[territory].segment,
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
                    f"Eversource {TERRITORIES[territory].name} "
                    f"{RATE_CLASS_NAMES[rate_class]}"
                )
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_TERRITORY, default="nh"): vol.In(
                    {key: item.name for key, item in TERRITORIES.items()}
                ),
                vol.Required(CONF_RATE_CLASS, default="r"): vol.In(RATE_CLASS_NAMES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
