"""Platform for sensor integration."""

from __future__ import annotations
import dataclasses
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    ACTIVE_ERRORS_SENSOR_TYPE,
    APPLIANCE_SENSOR_TYPES,
    CLIMATE_ZONE_SENSOR_TYPES,
    DOMAIN,
    HOT_WATER_ZONE_SENSOR_TYPES,
    PRODUCER_SENSOR_TYPES,
    PRODUCER_SENSORS_ENABLED_BY_DEFAULT,
    PRODUCER_TYPE_NAMES,
)
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENTINEL_TIMESTAMP_YEARS = {1}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Producers come from the daily energy statistics, which have no row for a
    # new day until the gateway's first report after midnight. Track which
    # producer sensors exist so the ones missing at setup are added later.
    known_producer_sensors: set[str] = set()

    def _new_producer_sensors() -> list[RemehaHomeSensor]:
        new_entities = []
        for appliance in coordinator.data["appliances"]:
            for entity in _producer_sensors(coordinator, appliance):
                if entity.unique_id not in known_producer_sensors:
                    known_producer_sensors.add(entity.unique_id)
                    new_entities.append(entity)
        return new_entities

    @callback
    def _async_add_new_producer_sensors() -> None:
        if new_entities := _new_producer_sensors():
            _LOGGER.debug("Adding %d producer sensors", len(new_entities))
            async_add_entities(new_entities)

    entities = []
    entities.extend(_new_producer_sensors())
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for entity_description in APPLIANCE_SENSOR_TYPES:
            entities.append(
                RemehaHomeSensor(coordinator, appliance_id, entity_description)
            )

        entities.append(
            RemehaHomeActiveErrorsSensor(
                coordinator, appliance_id, ACTIVE_ERRORS_SENSOR_TYPE
            )
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
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_producer_sensors)
    )


def _producer_sensors(
    coordinator: RemehaHomeUpdateCoordinator, appliance: dict
) -> list[RemehaHomeSensor]:
    """Create sensors for each producer (heat pump, backup heater, ...).

    Producers come from the daily energy statistics, so this returns nothing
    while there is no row for today. Fields the API reports as null for a
    producer (e.g. energy delivered by the backup heater) are skipped.
    """
    producers = appliance.get("producers") or {}
    type_counts: dict[str, int] = {}
    for producer in producers.values():
        producer_type = producer.get("producerType")
        type_counts[producer_type] = type_counts.get(producer_type, 0) + 1

    entities = []
    for producer_key, producer in producers.items():
        producer_type = producer["producerType"]
        label = PRODUCER_TYPE_NAMES.get(producer_type, producer_type)
        if type_counts[producer_type] > 1:
            label = f"{label} {producer.get('instanceWithinDevice') or 1}"
        enabled_keys = PRODUCER_SENSORS_ENABLED_BY_DEFAULT.get(producer_type, set())

        for description in PRODUCER_SENSOR_TYPES:
            if producer.get(description.key) is None:
                continue
            entities.append(
                RemehaHomeSensor(
                    coordinator,
                    appliance["applianceId"],
                    dataclasses.replace(
                        description,
                        key=f"producers.{producer_key}.{description.key}",
                        name=f"{label} {description.name}",
                        entity_registry_enabled_default=description.key
                        in enabled_keys,
                    ),
                )
            )
    return entities

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
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._data is not None

    @property
    def native_value(self):
        """Return the measurement value for this sensor."""
        value = self._data
        try:
            for part in self.entity_description.key.split("."):
                value = value[part]
        except (KeyError, TypeError):
            # The key is missing or a parent object is null; this is evaluated on
            # every state write, so keep it at debug level to avoid log spam.
            _LOGGER.debug("Key not found in data: %s", self.entity_description.key)
            return None

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
            if parsed.year in SENTINEL_TIMESTAMP_YEARS:
                return None
            # Only add timezone if the parsed datetime is naive
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return parsed

        if self.entity_description.device_class == SensorDeviceClass.DURATION:
            return _duration_minutes(value)

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


class RemehaHomeActiveErrorsSensor(RemehaHomeSensor):
    """Number of active appliance errors, with the raw list as an attribute."""

    @property
    def native_value(self) -> int | None:
        """Return the number of active errors."""
        errors = self._data.get("activeErrors")
        if errors is None:
            return None
        return len(errors)

    @property
    def icon(self) -> str:
        """Return an icon reflecting whether there are active errors."""
        if self.native_value:
            return "mdi:alert-circle"
        return "mdi:alert-circle-check-outline"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the active errors as reported by the API."""
        errors = self._data.get("activeErrors") or []
        return {
            "errors": errors,
            "error_codes": [
                error.get("errorCode")
                for error in errors
                if isinstance(error, dict) and error.get("errorCode") is not None
            ],
        }


def _duration_minutes(value) -> int | None:
    """Return an API duration ("HH:MM" or "HH:MM:SS") in minutes."""
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) < 2:
        return None
    return parts[0] * 60 + parts[1]
