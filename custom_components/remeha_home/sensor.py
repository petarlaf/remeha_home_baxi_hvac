"""Platform for sensor integration."""

from __future__ import annotations
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from . import RemehaHomeConfigEntry
from .const import (
    APPLIANCE_SENSOR_TYPES,
    CLIMATE_ZONE_SENSOR_TYPES,
    HOT_WATER_ZONE_SENSOR_TYPES,
)
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: RemehaHomeConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for entity_description in APPLIANCE_SENSOR_TYPES:
            entities.append(
                RemehaHomeSensor(coordinator, appliance_id, entity_description)
            )

        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            for entity_description in CLIMATE_ZONE_SENSOR_TYPES:
                entities.append(
                    RemehaHomeSensor(coordinator, climate_zone_id, entity_description)
                )

        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            for entity_description in HOT_WATER_ZONE_SENSOR_TYPES:
                entities.append(
                    RemehaHomeSensor(coordinator, hot_water_zone_id, entity_description)
                )

    async_add_entities(entities)


class RemehaHomeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        item_id: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Create a Remeha Home sensor entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.item_id = item_id
        self._attr_unique_id = "_".join([DOMAIN, self.item_id, entity_description.key])

    @property
    def _data(self):
        """Return the appliance data for this sensor."""
        return self.coordinator.get_by_id(self.item_id)

    @property
    def native_value(self):
        """Return the measurement value for this sensor."""
        data = self._data
        if data is None:
            return None
        try:
            for part in self.entity_description.key.split("."):
                data = data[part]
        except (KeyError, TypeError):
            _LOGGER.warning("Key not found in data: %s", self.entity_description.key)
            return None
        value = data

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            # Guard against None values (e.g. boostModeEndTime when not in boost mode)
            if value is None:
                return None
            parsed = dt_util.parse_datetime(value)
            if parsed is None:
                _LOGGER.warning(
                    "Could not parse timestamp value '%s' for sensor %s",
                    value,
                    self.entity_description.key,
                )
                return None
            # as_local() correctly converts a UTC-aware datetime to local time
            return dt_util.as_local(parsed)

        return value

    @property
    def icon(self) -> str | None:
        """Return a dynamic icon for the error status sensor."""
        if self.entity_description.key == "errorStatus":
            status = self.native_value
            if status and status.lower() not in ["idle", "ok", "noerror", "running"]:
                return "mdi:alert-circle-outline"
            return "mdi:check-circle"
        return self.entity_description.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.item_id)
