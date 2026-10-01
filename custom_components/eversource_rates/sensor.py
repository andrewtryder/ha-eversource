"""Sensor entities for the current Eversource tariff."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EversourceConfigEntry
from .binary_sensor import outage_device_info
from .const import DOMAIN, RATE_CLASS_NAMES, TERRITORIES
from .coordinator import EversourceRatesCoordinator
from .entity_ids import sensor_object_id
from .outage_coordinator import EversourceOutageCoordinator
from .tariffs import SERVICE_AREA_NAMES, SUPPLY_PLAN_NAMES

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

OUTAGE_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="customers_out",
        name="Customers Out",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="percent_out",
        name="Percent Out",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="customers_served",
        name="Customers Served",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
            part
            for part in (
                DOMAIN,
                coordinator.data.territory,
                coordinator.data.rate_class,
                coordinator.data.supply_plan,
                coordinator.data.service_area,
                description.key,
            )
            if part
        )
        # Assign the documented ID before Home Assistant registers the entity.
        # NH Rate R keeps historical short IDs; other tariffs include territory/rate.
        object_id = sensor_object_id(
            coordinator.data.territory,
            coordinator.data.rate_class,
            description.key,
            supply_plan=coordinator.data.supply_plan,
            service_area=coordinator.data.service_area,
        )
        self.entity_id = f"sensor.{object_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the logical Eversource tariff device."""
        rates = self.coordinator.data
        name_parts = [
            f"Eversource {TERRITORIES[rates.territory].name}",
            RATE_CLASS_NAMES[rates.rate_class],
        ]

        if rates.supply_plan:
            name_parts.append(SUPPLY_PLAN_NAMES[rates.supply_plan])
        if rates.service_area:
            name_parts.append(SERVICE_AREA_NAMES[rates.service_area])
        device_id_parts = [rates.territory, rates.rate_class]
        if rates.supply_plan:
            device_id_parts.append(rates.supply_plan)
        if rates.service_area:
            device_id_parts.append(rates.service_area)
        return DeviceInfo(
            identifiers={(DOMAIN, "_".join(device_id_parts))},
            name=" — ".join(name_parts),
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
            "supply_plan": rates.supply_plan,
            "service_area": rates.service_area,
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
    def available(self) -> bool:
        """Stay registered but unavailable when the rider disappears mid-session."""
        return (
            super().available
            and self.entity_description.key
            in self.coordinator.data.delivery.variable_components
        )

    @property
    def native_value(self) -> Decimal | None:
        """Return this rider's variable USD/kWh rate when present."""
        component = self.coordinator.data.delivery.variable_components.get(
            self.entity_description.key
        )
        if component is None:
            return None
        return component.rate


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EversourceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all stable known sensors and current parsed component sensors."""
    coordinator = entry.runtime_data.coordinator
    components = coordinator.data.delivery.variable_components
    known_components: set[str] = set(components)

    entities: list[SensorEntity] = [
        EversourceSensor(coordinator, description)
        for description in PRIMARY_DESCRIPTIONS
    ]
    entities.extend(
        EversourceComponentSensor(coordinator, key, f"Eversource {component.label}")
        for key, component in components.items()
    )
    async_add_entities(entities)

    @callback
    def _async_check_components() -> None:
        """Add sensors for any newly discovered delivery components."""
        if not coordinator.last_update_success or not coordinator.data:
            return
        current_components = coordinator.data.delivery.variable_components
        new_keys = [key for key in current_components if key not in known_components]
        if not new_keys:
            return
        known_components.update(new_keys)
        async_add_entities(
            [
                EversourceComponentSensor(
                    coordinator, key, f"Eversource {current_components[key].label}"
                )
                for key in new_keys
            ]
        )

    entry.async_on_unload(coordinator.async_add_listener(_async_check_components))

    outage_coordinator = entry.runtime_data.outage_coordinator
    if outage_coordinator is not None:
        entry_unique_id = entry.unique_id or entry.entry_id
        async_add_entities(
            [
                EversourceOutageSensor(
                    outage_coordinator,
                    description,
                    entry_unique_id,
                )
                for description in OUTAGE_SENSOR_DESCRIPTIONS
            ]
        )


class EversourceOutageSensor(
    CoordinatorEntity[EversourceOutageCoordinator], SensorEntity
):
    """Aggregate outage metric sensor for a municipality."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EversourceOutageCoordinator,
        description: SensorEntityDescription,
        entry_unique_id: str,
    ) -> None:
        """Initialize one outage metric sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_unique_id}_{description.key}"
        self._attr_name = description.name
        self._attr_device_info = outage_device_info(
            entry_unique_id, coordinator.municipality
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the current outage metric."""
        data = self.coordinator.data
        if self.entity_description.key == "customers_out":
            return data.customers_out
        if self.entity_description.key == "percent_out":
            return data.percent_out
        if self.entity_description.key == "customers_served":
            return data.customers_served
        return None
