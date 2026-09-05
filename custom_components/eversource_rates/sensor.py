"""Sensor entities for the current Eversource tariff."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EversourceConfigEntry
from .const import DOMAIN, RATE_CLASS_NAMES, TERRITORIES
from .coordinator import EversourceRatesCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

USD_PER_KWH = "USD/kWh"
USD_PER_MONTH = "USD/month"

PRIMARY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="supply_rate",
        name="Eversource Supply Rate",
        native_unit_of_measurement=USD_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="delivery_rate",
        name="Eversource Delivery Rate",
        native_unit_of_measurement=USD_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_electricity_rate",
        name="Eversource Total Electricity Rate",
        native_unit_of_measurement=USD_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="customer_charge",
        name="Eversource Customer Charge",
        native_unit_of_measurement=USD_PER_MONTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


class EversourceSensor(CoordinatorEntity[EversourceRatesCoordinator], SensorEntity):
    """A primary current-tariff sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EversourceRatesCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a primary tariff sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = "_".join(
            (
                DOMAIN,
                coordinator.data.territory,
                coordinator.data.rate_class,
                description.key,
            )
        )
        # Assign the documented ID before Home Assistant registers the entity.
        # This keeps automations independent of the territory/rate-class device name.
        self.entity_id = f"sensor.eversource_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the logical Eversource tariff device."""
        rates = self.coordinator.data
        name = (
            f"Eversource {TERRITORIES[rates.territory].name} "
            f"{RATE_CLASS_NAMES[rates.rate_class]}"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, f"{rates.territory}_{rates.rate_class}")},
            name=name,
            manufacturer="Eversource",
            model=RATE_CLASS_NAMES[rates.rate_class],
            configuration_url=rates.source_supply_url,
        )

    @property
    def native_value(self) -> Decimal:
        """Return the exact rate represented by this sensor."""
        rates = self.coordinator.data
        values = {
            "supply_rate": rates.supply.rate,
            "delivery_rate": rates.delivery.variable_rate,
            "total_electricity_rate": rates.total_variable_rate,
            "customer_charge": rates.delivery.customer_charge,
        }
        return values[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return concise public tariff provenance for the total-rate sensor."""
        rates = self.coordinator.data
        if self.entity_description.key != "total_electricity_rate":
            return {}
        return {
            "territory": rates.territory,
            "rate_class": rates.rate_class.upper(),
            "supply_rate": str(rates.supply.rate),
            "delivery_rate": str(rates.delivery.variable_rate),
            "supply_effective_date": rates.supply.effective_date.isoformat()
            if rates.supply.effective_date
            else None,
            "supply_expiration_date": rates.supply.expiration_date.isoformat()
            if rates.supply.expiration_date
            else None,
            "retrieved_at": rates.retrieved_at.isoformat(),
            "source_supply_url": rates.source_supply_url,
            "source_delivery_url": rates.source_delivery_url,
        }


class EversourceComponentSensor(EversourceSensor):
    """A disabled-by-default transparent delivery component sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: EversourceRatesCoordinator, key: str, name: str
    ) -> None:
        """Initialize one disabled-by-default delivery-rider sensor."""
        super().__init__(
            coordinator,
            SensorEntityDescription(
                key=key,
                name=name,
                native_unit_of_measurement=USD_PER_KWH,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )

    @property
    def native_value(self) -> Decimal:
        """Return this rider's variable USD/kWh rate."""
        return self.coordinator.data.delivery.variable_components[
            self.entity_description.key
        ].rate


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EversourceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all stable known sensors and current parsed component sensors."""
    coordinator = entry.runtime_data.coordinator
    components = coordinator.data.delivery.variable_components
    entities = [
        EversourceSensor(coordinator, description)
        for description in PRIMARY_DESCRIPTIONS
    ]
    entities.extend(
        EversourceComponentSensor(coordinator, key, f"Eversource {component.label}")
        for key, component in components.items()
    )
    async_add_entities(entities)
