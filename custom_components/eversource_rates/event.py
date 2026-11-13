"""Activity event entities for successful checks, changes, and failures."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor import outage_device_info
from .coordinator import EversourceRatesCoordinator
from .models import EversourceRates
from .outage_coordinator import EversourceOutageCoordinator
from .outage_models import EversourceOutageArea
from .sensor import rate_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import EversourceConfigEntry


class _EversourceActivityEvent(EventEntity):
    """Publish poll results as events visible on device Activity cards."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _publish(self, event_type: str, message: str, **details: Any) -> None:
        """Record an event even if the checked values have not changed."""
        self._trigger_event(event_type, {"message": message, **details})
        self.async_write_ha_state()


class EversourceRatesActivityEvent(_EversourceActivityEvent):
    """Show each tariff poll and significant transitions on the rate device."""

    _attr_name = "Rate activity"
    _attr_icon = "mdi:clipboard-check-clock-outline"
    _attr_event_types = [
        "rates_checked",
        "rates_changed",
        "rate_check_failed",
        "rate_check_recovered",
    ]

    def __init__(
        self,
        coordinator: EversourceRatesCoordinator,
        entry_unique_id: str,
    ) -> None:
        """Initialize a stable activity event on the tariff device."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_unique_id}_rate_activity"
        self._attr_device_info = rate_device_info(coordinator.data)
        self._previous_data = coordinator.data
        self._previous_success = coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Subscribe to refreshes and report the initial successful check."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._on_refresh))
        self._publish(
            "rates_checked",
            "Initial Eversource rates check succeeded",
            **self._rate_details(self.coordinator.data),
        )

    @staticmethod
    def _rate_details(rates: EversourceRates) -> dict[str, str]:
        """Keep the source prices and their timestamp on each event."""
        return {
            "total_rate_usd_per_kwh": str(rates.total_variable_rate),
            "supply_rate_usd_per_kwh": str(rates.supply.rate),
            "delivery_rate_usd_per_kwh": str(rates.delivery.variable_rate),
            "customer_charge_usd_per_month": str(rates.delivery.customer_charge),
            "retrieved_at": rates.retrieved_at.isoformat(),
        }

    @callback
    def _on_refresh(self) -> None:
        """Emit one activity event for each successful poll or failure transition."""
        if not self.coordinator.last_update_success:
            if self._previous_success:
                error = self.coordinator.last_exception
                self._publish(
                    "rate_check_failed",
                    "Eversource rates check failed",
                    error=str(error)[:200] if error else "Unknown error",
                )
            self._previous_success = False
            return

        rates = self.coordinator.data
        details = self._rate_details(rates)
        if not self._previous_success:
            event_type = "rate_check_recovered"
            message = "Eversource rates checks recovered"
        elif (
            rates.supply.rate != self._previous_data.supply.rate
            or rates.delivery.variable_rate
            != self._previous_data.delivery.variable_rate
            or rates.delivery.customer_charge
            != self._previous_data.delivery.customer_charge
        ):
            event_type = "rates_changed"
            message = "Eversource rates changed"
            details["previous_total_rate_usd_per_kwh"] = str(
                self._previous_data.total_variable_rate
            )
        else:
            event_type = "rates_checked"
            message = "Eversource rates checked; prices unchanged"

        self._publish(event_type, message, **details)
        self._previous_data = rates
        self._previous_success = True


class EversourceOutageActivityEvent(_EversourceActivityEvent):
    """Show every municipality outage check, including all-clear polls."""

    _attr_name = "Outage activity"
    _attr_icon = "mdi:transmission-tower"
    _attr_event_types = [
        "outage_checked",
        "outage_detected",
        "outage_cleared",
        "outage_count_changed",
        "outage_check_failed",
        "outage_check_recovered",
    ]

    def __init__(
        self,
        coordinator: EversourceOutageCoordinator,
        entry_unique_id: str,
    ) -> None:
        """Initialize a stable event on the municipality outage device."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_unique_id}_outage_activity"
        self._attr_device_info = outage_device_info(
            entry_unique_id, coordinator.municipality
        )
        self._previous_data = coordinator.data
        self._previous_success = coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Subscribe to refreshes and report initial success or failure."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._on_refresh))
        if self.coordinator.last_update_success and self.coordinator.data:
            self._publish(
                "outage_checked",
                "Initial municipality outage check succeeded",
                **self._outage_details(self.coordinator.data),
            )
        else:
            self._publish(
                "outage_check_failed",
                "Initial municipality outage check failed",
                municipality=self.coordinator.municipality,
            )

    @staticmethod
    def _outage_details(area: EversourceOutageArea) -> dict[str, Any]:
        """Describe aggregate municipal reports, not household power status."""
        return {
            "municipality": area.area_name.title(),
            "customers_out": area.customers_out,
            "customers_served": area.customers_served,
            "percent_out": area.percent_out,
            "retrieved_at": area.retrieved_at.isoformat(),
        }

    @callback
    def _on_refresh(self) -> None:
        """Record checks every polling interval and transitions in outage counts."""
        if not self.coordinator.last_update_success:
            if self._previous_success:
                error = self.coordinator.last_exception
                self._publish(
                    "outage_check_failed",
                    "Municipality outage check failed",
                    municipality=self.coordinator.municipality,
                    error=str(error)[:200] if error else "Unknown error",
                )
            self._previous_success = False
            return

        area = self.coordinator.data
        details = self._outage_details(area)
        prior = self._previous_data
        if prior is not None and prior.customers_out != area.customers_out:
            details["previous_customers_out"] = prior.customers_out
            if prior.customers_out == 0:
                event_type = "outage_detected"
                message = "Municipality outages reported"
            elif area.customers_out == 0:
                event_type = "outage_cleared"
                message = "No municipality outages currently reported"
            else:
                event_type = "outage_count_changed"
                message = "Municipality outage count changed"
        elif not self._previous_success:
            event_type = "outage_check_recovered"
            message = "Municipality outage checks recovered"
        else:
            event_type = "outage_checked"
            message = "Municipality outage check succeeded"

        self._publish(event_type, message, **details)
        self._previous_data = area
        self._previous_success = True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EversourceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Attach activity entities to the same devices as tariffs and outages."""
    entry_unique_id = entry.unique_id or entry.entry_id
    entities: list[EventEntity] = [
        EversourceRatesActivityEvent(
            entry.runtime_data.coordinator,
            entry_unique_id,
        )
    ]
    if outage_coordinator := entry.runtime_data.outage_coordinator:
        entities.append(
            EversourceOutageActivityEvent(outage_coordinator, entry_unique_id)
        )
    async_add_entities(entities)
