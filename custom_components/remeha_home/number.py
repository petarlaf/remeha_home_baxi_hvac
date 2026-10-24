"""Platform for number integration (heating curve and activity temperatures)."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home number entities from a config entry."""
    api: RemehaHomeAPI = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: RemehaHomeUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[NumberEntity] = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]

            if climate_zone.get("heatingCurve"):
                entities.append(
                    RemehaHomeHeatingCurveNumber(
                        api, coordinator, climate_zone_id, "slope"
                    )
                )
                entities.append(
                    RemehaHomeHeatingCurveNumber(
                        api, coordinator, climate_zone_id, "baseSetpoint"
                    )
                )

            for activity in climate_zone.get("activities") or []:
                entities.append(
                    RemehaHomeActivityTemperatureNumber(
                        api,
                        coordinator,
                        climate_zone_id,
                        activity["type"],
                        activity["activityNumber"],
                        enabled_default=activity["type"] == "Heating"
                        or bool(climate_zone.get("capabilityCooling")),
                    )
                )

    async_add_entities(entities)


class RemehaHomeZoneNumber(CoordinatorEntity, NumberEntity):
    """Base class for numbers that belong to a climate zone."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
    ) -> None:
        """Create a climate zone number entity."""
        super().__init__(coordinator)
        self.api = api
        self.climate_zone_id = climate_zone_id

    @property
    def _data(self) -> dict | None:
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)

    async def _async_after_write(self) -> None:
        self.coordinator.invalidate_zone_settings(self.climate_zone_id)
        await self.coordinator.async_request_refresh()


class RemehaHomeHeatingCurveNumber(RemehaHomeZoneNumber):
    """Slope or base setpoint of a zone's heating curve."""

    _attr_entity_category = EntityCategory.CONFIG

    # field -> (name, min key, max key, step key, unit)
    FIELDS = {
        "slope": (
            "Heating Curve Slope",
            "minimumSlope",
            "maximumSlope",
            "incrementSlope",
            None,
        ),
        "baseSetpoint": (
            "Heating Curve Base Setpoint",
            "minimumBaseSetpoint",
            "maximumBaseSetpoint",
            "incrementBaseSetpoint",
            UnitOfTemperature.CELSIUS,
        ),
    }

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
        field: str,
    ) -> None:
        """Create a heating curve number entity."""
        super().__init__(api, coordinator, climate_zone_id)
        self.field = field
        name, self._min_key, self._max_key, self._step_key, unit = self.FIELDS[field]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:chart-bell-curve-cumulative"
        self._attr_unique_id = f"{DOMAIN}_{climate_zone_id}_heatingCurve_{field}"

    @property
    def _curve(self) -> dict | None:
        return (self._data or {}).get("heatingCurve")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and bool(self._curve)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return (self._curve or {}).get(self.field)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value reported by the API."""
        return (self._curve or {}).get(self._min_key, 0)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value reported by the API."""
        return (self._curve or {}).get(self._max_key, 100)

    @property
    def native_step(self) -> float:
        """Return the step reported by the API."""
        return (self._curve or {}).get(self._step_key) or 0.1

    @property
    def extra_state_attributes(self) -> dict:
        """Return the maximum flow temperature for context."""
        return {"max_flow_temperature": (self._curve or {}).get("maxFlowTemperature")}

    async def async_set_native_value(self, value: float) -> None:
        """Send the heating curve with this field changed."""
        curve = self._curve
        if not curve:
            return
        slope = value if self.field == "slope" else curve["slope"]
        base_setpoint = value if self.field == "baseSetpoint" else curve["baseSetpoint"]
        _LOGGER.debug(
            "Setting heating curve of zone %s to slope %s, base setpoint %s",
            self.climate_zone_id,
            slope,
            base_setpoint,
        )
        await self.api.async_set_heating_curve(
            self.climate_zone_id, round(slope, 2), round(base_setpoint, 1)
        )
        await self._async_after_write()


class RemehaHomeActivityTemperatureNumber(RemehaHomeZoneNumber):
    """Temperature of one schedule activity (preset) in a climate zone."""

    _attr_device_class = None
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
        activity_type: str,
        activity_number: int,
        enabled_default: bool,
    ) -> None:
        """Create an activity temperature number entity."""
        super().__init__(api, coordinator, climate_zone_id)
        self.activity_type = activity_type
        self.activity_number = activity_number
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_icon = (
            "mdi:snowflake-thermometer"
            if activity_type == "Cooling"
            else "mdi:home-thermometer"
        )
        self._attr_unique_id = (
            f"{DOMAIN}_{climate_zone_id}_activity_{activity_type}_{activity_number}"
        )

    @property
    def _activities(self) -> list:
        return (self._data or {}).get("activities") or []

    @property
    def _activity(self) -> dict | None:
        return next(
            (
                activity
                for activity in self._activities
                if activity.get("type") == self.activity_type
                and activity.get("activityNumber") == self.activity_number
            ),
            None,
        )

    @property
    def name(self) -> str:
        """Return the activity name, using the custom name when one is set."""
        custom_name = ((self._activity or {}).get("name") or "").strip()
        label = custom_name or f"Activity {self.activity_number}"
        return f"{self.activity_type} {label} Temperature"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._activity is not None

    @property
    def native_value(self) -> float | None:
        """Return the activity temperature."""
        return (self._activity or {}).get("temperature")

    @property
    def native_min_value(self) -> float:
        """Return the minimum temperature reported by the API."""
        return (self._activity or {}).get("setPointMin", 5)

    @property
    def native_max_value(self) -> float:
        """Return the maximum temperature reported by the API."""
        return (self._activity or {}).get("setPointMax", 30)

    @property
    def native_step(self) -> float:
        """Return the step reported by the API."""
        return (self._activity or {}).get("increment") or 0.5

    async def async_set_native_value(self, value: float) -> None:
        """Send the full activity list with this temperature changed."""
        activities = [dict(activity) for activity in self._activities]
        if not activities or self._activity is None:
            return
        for activity in activities:
            if (
                activity.get("type") == self.activity_type
                and activity.get("activityNumber") == self.activity_number
            ):
                activity["temperature"] = value
        _LOGGER.debug(
            "Setting %s activity %s of zone %s to %s",
            self.activity_type,
            self.activity_number,
            self.climate_zone_id,
            value,
        )
        await self.api.async_set_activities(self.climate_zone_id, activities)
        await self._async_after_write()
