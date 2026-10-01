"""Binary sensor platform for Eversource municipality outage monitoring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .outage_coordinator import EversourceOutageCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import EversourceConfigEntry

OUTAGE_MAP_URL = "https://outagemap.eversource.com/external/default.html"


def outage_device_info(territory: str, municipality: str) -> DeviceInfo:
    """Return shared DeviceInfo for municipality outage entities."""
    slug = slugify(municipality)
    display_name = municipality.title()
    return DeviceInfo(
        identifiers={(DOMAIN, f"{territory}_{slug}_outage")},
        name=f"Eversource {display_name} Outage",
        manufacturer="Eversource",
        model="Outage reporting",
        configuration_url=OUTAGE_MAP_URL,
    )


class EversourceOutageBinarySensor(
    CoordinatorEntity[EversourceOutageCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if any customers are out in the municipality."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EversourceOutageCoordinator,
        territory: str,
        municipality: str,
    ) -> None:
        """Initialize the outage binary sensor."""
        super().__init__(coordinator)
        self._territory = territory
        self._municipality = municipality
        slug = slugify(municipality)
        self._attr_unique_id = f"{DOMAIN}_{territory}_{slug}_outage"
        self.entity_id = f"binary_sensor.eversource_{territory}_{slug}_outage"
        self._attr_name = f"Eversource {municipality.title()} Outage"
        self._attr_device_info = outage_device_info(territory, municipality)

    @property
    def is_on(self) -> bool:
        """Return True if at least one customer is reported without power."""
        return self.coordinator.data.customers_out > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return provenance and aggregate metrics for the municipality."""
        data = self.coordinator.data
        return {
            "municipality": data.area_name,
            "territory": data.territory,
            "customers_out": data.customers_out,
            "customers_served": data.customers_served,
            "percent_out": data.percent_out,
            "retrieved_at": data.retrieved_at.isoformat(),
            "source_url": data.source_url,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EversourceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Eversource outage binary sensor if configured."""
    outage_coordinator = entry.runtime_data.outage_coordinator
    if outage_coordinator is None:
        return

    async_add_entities(
        [
            EversourceOutageBinarySensor(
                outage_coordinator,
                outage_coordinator.territory,
                outage_coordinator.municipality,
            )
        ]
    )
