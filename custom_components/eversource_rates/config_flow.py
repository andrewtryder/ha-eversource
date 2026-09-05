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
    CONF_SERVICE_AREA,
    CONF_SUPPLY_PLAN,
    CONF_TERRITORY,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    RATE_CLASS_NAMES,
    TERRITORIES,
    update_interval_hours_from_options,
    update_interval_options,
)
from .tariffs import (
    SERVICE_AREA_NAMES,
    SUPPLY_PLAN_NAMES,
    TariffSelection,
    entry_unique_id,
    get_tariff_definition,
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


def _supply_plan_options(territory: str, rate_class: str) -> dict[str, str]:
    definition = get_tariff_definition(territory, rate_class)
    if definition is None:
        return {}
    return {
        plan: SUPPLY_PLAN_NAMES[plan]
        for plan in definition.supply_plans
        if plan in SUPPLY_PLAN_NAMES
    }


def _service_area_options(territory: str, rate_class: str) -> dict[str, str]:
    definition = get_tariff_definition(territory, rate_class)
    if definition is None:
        return {}
    return {
        area: SERVICE_AREA_NAMES[area]
        for area in definition.service_areas
        if area in SERVICE_AREA_NAMES
    }


class EversourceRatesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up a known, public Eversource tariff without user credentials."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize transient multi-step selection state."""
        self._territory: str | None = None
        self._rate_class: str | None = None
        self._supply_plan: str | None = None
        self._service_area: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow (reload-on-save; no update listener)."""
        return EversourceRatesOptionsFlow()

    def _selection(self) -> TariffSelection:
        assert self._territory is not None
        assert self._rate_class is not None
        return TariffSelection(
            territory=self._territory,
            rate_class=self._rate_class,
            supply_plan=self._supply_plan,
            service_area=self._service_area,
        )

    async def _async_finalize(self):
        """Validate connectivity and create the config entry."""
        selection = self._selection()
        await self.async_set_unique_id(entry_unique_id(selection))
        self._abort_if_unique_id_configured()
        await EversourceClient(
            async_get_clientsession(self.hass),
            selection=selection,
        ).async_get_rates()
        title_parts = [
            f"Eversource {TERRITORIES[selection.territory].name}",
            RATE_CLASS_NAMES[selection.rate_class],
        ]
        if selection.supply_plan:
            title_parts.append(SUPPLY_PLAN_NAMES[selection.supply_plan])
        if selection.service_area:
            title_parts.append(SERVICE_AREA_NAMES[selection.service_area])
        data = {
            CONF_TERRITORY: selection.territory,
            CONF_RATE_CLASS: selection.rate_class,
        }
        if selection.supply_plan:
            data[CONF_SUPPLY_PLAN] = selection.supply_plan
        if selection.service_area:
            data[CONF_SERVICE_AREA] = selection.service_area
        return self.async_create_entry(title=" — ".join(title_parts), data=data)

    def _map_client_error(self, err: Exception) -> str | None:
        if isinstance(err, EversourceConnectionError):
            return "cannot_connect"
        if isinstance(err, EversourceTariffParseError):
            return "invalid_tariff_data"
        if isinstance(err, EversourceUnsupportedTariffError):
            return "unsupported_tariff"
        return None

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
            return self.async_abort(reason="unsupported_tariff")
        errors: dict[str, str] = {}
        if user_input is not None:
            rate_class = user_input[CONF_RATE_CLASS]
            if rate_class not in options:
                errors["base"] = "unsupported_tariff"
            else:
                self._rate_class = rate_class
                definition = get_tariff_definition(self._territory, rate_class)
                if definition and definition.supply_plans:
                    return await self.async_step_supply_plan()
                if definition and definition.service_areas:
                    return await self.async_step_service_area()
                try:
                    return await self._async_finalize()
                except (
                    EversourceConnectionError,
                    EversourceTariffParseError,
                    EversourceUnsupportedTariffError,
                ) as err:
                    errors["base"] = self._map_client_error(err) or "unsupported_tariff"

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

    async def async_step_supply_plan(self, user_input=None):
        """Select Fixed vs Monthly Variable Basic Service when required."""
        assert self._territory is not None
        assert self._rate_class is not None
        options = _supply_plan_options(self._territory, self._rate_class)
        if not options:
            return self.async_abort(reason="unsupported_tariff")
        errors: dict[str, str] = {}
        if user_input is not None:
            supply_plan = user_input[CONF_SUPPLY_PLAN]
            if supply_plan not in options:
                errors["base"] = "unsupported_tariff"
            else:
                self._supply_plan = supply_plan
                definition = get_tariff_definition(self._territory, self._rate_class)
                if definition and definition.service_areas:
                    return await self.async_step_service_area()
                try:
                    return await self._async_finalize()
                except (
                    EversourceConnectionError,
                    EversourceTariffParseError,
                    EversourceUnsupportedTariffError,
                ) as err:
                    errors["base"] = self._map_client_error(err) or "unsupported_tariff"

        default_plan = next(iter(options))
        return self.async_show_form(
            step_id="supply_plan",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SUPPLY_PLAN, default=default_plan): vol.In(
                        options
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_service_area(self, user_input=None):
        """Select EMA service area when Energy Efficiency charges differ."""
        assert self._territory is not None
        assert self._rate_class is not None
        options = _service_area_options(self._territory, self._rate_class)
        if not options:
            return self.async_abort(reason="unsupported_tariff")
        errors: dict[str, str] = {}
        if user_input is not None:
            service_area = user_input[CONF_SERVICE_AREA]
            if service_area not in options:
                errors["base"] = "unsupported_tariff"
            else:
                self._service_area = service_area
                try:
                    return await self._async_finalize()
                except (
                    EversourceConnectionError,
                    EversourceTariffParseError,
                    EversourceUnsupportedTariffError,
                ) as err:
                    errors["base"] = self._map_client_error(err) or "unsupported_tariff"

        default_area = next(iter(options))
        return self.async_show_form(
            step_id="service_area",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE_AREA, default=default_area): vol.In(
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
