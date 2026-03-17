"""Water Heater platform for Remeha Home hot water zones.

Based on the data provided by the dashboard API, the relevant fields are:
  - current temperature: "dhwTemperature"
  - target temperature: "targetSetpoint"
  - min/max temperature: "setPointMin"/"setPointMax" (optional)
  - current operation mode: "dhwZoneMode" (e.g. Scheduling, Comfort, Eco, or Boost)
"""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator
from .api import RemehaHomeAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up water heater entities for the Remeha Home integration."""
    coordinator: RemehaHomeUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: RemehaHomeAPI = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for hot_water_zone in appliance.get("hotWaterZones", []):
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            entities.append(
                RemehaHomeWaterHeater(api, coordinator, hot_water_zone_id)
            )
    async_add_entities(entities)


class RemehaHomeWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of a Water Heater for a Remeha Home hot water zone.

    Operation modes:
    - Boost: Temporarily boosts water heating to comfort temperature for 30 minutes.
             Only available when the current mode is Scheduled.
    - Scheduled: Follows the programmed schedule for water heating.
    - Comfort: Maintains water at comfort temperature continuously.
    - Eco: Maintains water at reduced temperature (anti-frost).
    """

    # Support target temperature and operation mode control.
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        hot_water_zone_id: str,
    ) -> None:
        """Initialize a water heater entity representing a Remeha Home hot water zone."""
        super().__init__(coordinator)
        self.api = api
        self.hot_water_zone_id = hot_water_zone_id
        self._attr_unique_id = f"{DOMAIN}_{hot_water_zone_id}"

    @property
    def _data(self) -> dict:
        """Return the hot water zone data from the coordinator."""
        return self.coordinator.get_by_id(self.hot_water_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the water heater."""
        return self.coordinator.get_device_info(self.hot_water_zone_id)

    @property
    def current_temperature(self) -> float | None:
        """Return the current water temperature."""
        return self._data.get("dhwTemperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the current target setpoint temperature depending on the active mode.

        - Scheduled: use "targetSetpoint"
        - Eco: use "reducedSetpoint"
        - Comfort: use "comfortSetPoint"
        """
        current_mode = self.current_operation
        if current_mode == "Scheduled":
            return self._data.get("targetSetpoint")
        elif current_mode == "Eco":
            return self._data.get("reducedSetpoint")
        elif current_mode == "Comfort":
            return self._data.get("comfortSetPoint")
        return None

    @property
    def min_temp(self) -> float | None:
        """Return the minimum temperature allowed for the water heater."""
        current_mode = self.current_operation
        set_point_ranges = self._data.get("setPointRanges", {})
        if current_mode == "Eco":
            return set_point_ranges.get("reducedSetpointMin", self._data.get("setPointMin"))
        elif current_mode == "Comfort":
            return set_point_ranges.get("comfortSetpointMin", self._data.get("setPointMin"))
        return self._data.get("setPointMin")

    @property
    def max_temp(self) -> float | None:
        """Return the maximum temperature allowed for the water heater."""
        current_mode = self.current_operation
        set_point_ranges = self._data.get("setPointRanges", {})
        if current_mode == "Eco":
            return set_point_ranges.get("reducedSetpointMax", self._data.get("setPointMax"))
        elif current_mode == "Comfort":
            return set_point_ranges.get("comfortSetpointMax", self._data.get("setPointMax"))
        return self._data.get("setPointMax")

    @property
    def current_operation(self) -> str:
        """Return the current operation mode (Scheduled, Comfort, Eco, or Boost)."""
        raw_mode = self._data.get("dhwZoneMode", "Unknown")
        mode_mapping = {
            "continuouscomfort": "Comfort",
            "off": "Eco",
            "scheduling": "Scheduled",
            "boost": "Boost",
        }
        return mode_mapping.get(raw_mode.lower(), raw_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for the water heater entity."""
        attributes: dict[str, Any] = {}

        # Add remaining boost time if in boost mode
        if self.current_operation == "Boost":
            boost_end_time = self._data.get("boostModeEndTime")
            if boost_end_time:
                try:
                    end_time = dt_util.parse_datetime(boost_end_time)
                    if end_time is not None:
                        now = dt_util.utcnow()
                        remaining_seconds = (end_time - now).total_seconds()
                        if remaining_seconds > 0:
                            remaining_minutes = int(remaining_seconds / 60)
                            attributes["remaining_boost_time"] = f"{remaining_minutes} minutes"
                except Exception as e:  # noqa: BLE001
                    _LOGGER.warning("Error calculating remaining boost time: %s", e)

        return attributes

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes.

        Boost is only available when the current mode is Scheduled.
        """
        if self.current_operation == "Scheduled":
            return ["Boost", "Scheduled", "Comfort", "Eco"]
        return ["Scheduled", "Comfort", "Eco"]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature for the water heater.

        Only available in Comfort or Eco mode.
        """
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        current_mode = self.current_operation
        _LOGGER.debug("Attempting to set temperature to %s in mode %s", temperature, current_mode)
        if current_mode == "Comfort":
            await self.api.async_set_hot_water_comfort_setpoint(self.hot_water_zone_id, temperature)
        elif current_mode == "Eco":
            await self.api.async_set_hot_water_reduced_setpoint(self.hot_water_zone_id, temperature)
        else:
            _LOGGER.warning("Temperature cannot be set when in mode: %s", current_mode)
            return

        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new operation mode for the water heater."""
        _LOGGER.debug("Setting hot water operation mode to %s", operation_mode)
        op_mode = operation_mode.lower()
        if op_mode == "boost":
            current_mode = self.current_operation
            if current_mode != "Scheduled":
                _LOGGER.warning(
                    "Boost mode can only be activated when in Scheduled mode. Current mode: %s",
                    current_mode,
                )
                return
            await self.api.async_set_hot_water_boost(self.hot_water_zone_id)
        elif op_mode == "scheduled":
            await self.api.async_set_hot_water_schedule(self.hot_water_zone_id)
        elif op_mode == "comfort":
            await self.api.async_set_hot_water_comfort(self.hot_water_zone_id)
        elif op_mode == "eco":
            await self.api.async_set_hot_water_eco(self.hot_water_zone_id)
        else:
            _LOGGER.error("Unknown hot water mode: %s", operation_mode)
            return

        await self.coordinator.async_request_refresh()
