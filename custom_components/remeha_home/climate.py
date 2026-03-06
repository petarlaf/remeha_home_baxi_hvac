"""Platform for Remeha Home climate integration."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RemehaHomeConfigEntry
from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Mappings for appliance operating mode ↔ HVAC mode
OPERATING_MODE_TO_HVAC_MODE = {
    "AutomaticCoolingHeating": HVACMode.HEAT,
    "ForcedCooling": HVACMode.COOL,
    "FrostProtection": HVACMode.OFF,
}

HVAC_MODE_TO_OPERATING_MODE = {
    HVACMode.HEAT: "AutomaticCoolingHeating",
    HVACMode.COOL: "ForcedCooling",
}

# Allowed preset modes
ALLOWED_PRESET_MODES = ["manual", "schedule1", "schedule2", "schedule3"]

# HVAC action mapping based on activeComfortDemand returned from the API
REMEHA_STATUS_TO_HVAC_ACTION = {
    "ProducingHeat": HVACAction.HEATING,
    "Idle": HVACAction.IDLE,
    "ProducingCold": HVACAction.COOLING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemehaHomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Remeha Home climate entity from a config entry."""
    api: RemehaHomeAPI = entry.runtime_data.api
    coordinator: RemehaHomeUpdateCoordinator = entry.runtime_data.coordinator

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            entities.append(
                RemehaHomeClimateEntity(api, coordinator, appliance_id, climate_zone_id)
            )

    async_add_entities(entities)


class RemehaHomeClimateEntity(CoordinatorEntity, ClimateEntity):
    """Climate entity representing a Remeha Home climate zone."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "remeha_home"

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        climate_zone_id: str,
    ) -> None:
        """Create a Remeha Home climate entity."""
        super().__init__(coordinator)
        self.api = api
        self.coordinator = coordinator
        self.appliance_id = appliance_id
        self.climate_zone_id = climate_zone_id

        self._attr_unique_id = "_".join([DOMAIN, self.climate_zone_id])
        self._requested_hvac_mode: HVACMode | None = None
        self._requested_hvac_mode_polls: int = 0

    @property
    def _data(self) -> dict:
        """Return the climate zone information from the coordinator."""
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._data["roomTemperature"]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return self._data["setPoint"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._data["setPointMin"]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._data["setPointMax"]

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return the current HVAC mode."""
        # Use the override if available (set optimistically after a user action)
        if self._requested_hvac_mode is not None:
            return self._requested_hvac_mode

        zone_data = self._data

        # The true mode of the zone is reported in 'zoneMode'.
        # If it's 'FrostProtection', the zone is OFF regardless of appliance operatingMode.
        if zone_data.get("zoneMode") == "FrostProtection":
            return HVACMode.OFF

        # If the zone is active, determine HEAT or COOL from the appliance's operatingMode.
        appliance_data = self.coordinator.get_by_id(self.appliance_id)
        operating_mode = appliance_data.get("operatingMode")

        if operating_mode is None:
            return HVACMode.OFF

        return OPERATING_MODE_TO_HVAC_MODE.get(operating_mode, HVACMode.OFF)

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of available HVAC modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return HVAC action based on the activeComfortDemand field from the API."""
        active_comfort = self._data.get("activeComfortDemand")
        if active_comfort in REMEHA_STATUS_TO_HVAC_ACTION:
            return REMEHA_STATUS_TO_HVAC_ACTION[active_comfort]
        # Fallback logic based on current mode
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        elif self.hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        elif self.hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the preset mode.

        'manual' when the zone is in manual mode.
        'schedule1/2/3' when in schedule mode, based on the active program number.
        """
        zone_mode = self._data.get("zoneMode")
        if self.hvac_mode == HVACMode.OFF:
            return None

        if zone_mode == "Manual":
            return "manual"
        if zone_mode in ["Scheduling", "TemporaryOverride"]:
            program = self._data.get("activeHeatingClimateTimeProgramNumber")
            if program in [1, 2, 3]:
                return f"schedule{program}"
        return None

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset modes."""
        return ALLOWED_PRESET_MODES

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temperature to %f", temperature)
            if self.hvac_mode != HVACMode.OFF:
                await self.api.async_set_manual(self.climate_zone_id, temperature)
                await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC operating mode.

        For HEAT and COOL we use the operating mode API on the appliance.
        For OFF we use the anti-frost API on the zone.
        """
        _LOGGER.debug("Setting HVAC mode to %s", hvac_mode)
        if hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            mode_payload = HVAC_MODE_TO_OPERATING_MODE[hvac_mode]
            await self.api.async_set_operating_mode(self.appliance_id, mode_payload)
            self._requested_hvac_mode = hvac_mode
            self._requested_hvac_mode_polls = 0
        elif hvac_mode == HVACMode.OFF:
            await self.api.async_set_off(self.climate_zone_id)
            self._requested_hvac_mode = HVACMode.OFF
            self._requested_hvac_mode_polls = 0
        else:
            raise NotImplementedError(f"Unsupported HVAC mode: {hvac_mode}")

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode.

        'manual' calls the manual API with the current target temperature.
        'schedule1/2/3' calls the schedule API with the corresponding program id.
        """
        _LOGGER.debug("Setting preset mode to %s", preset_mode)
        preset_mode = preset_mode.lower()
        if preset_mode not in ALLOWED_PRESET_MODES:
            _LOGGER.error("Preset mode %s is not allowed", preset_mode)
            return

        if preset_mode == "manual":
            if self.target_temperature is None:
                _LOGGER.warning("Cannot set manual preset: target temperature is unavailable")
                return
            await self.api.async_set_manual(self.climate_zone_id, self.target_temperature)
        else:
            heating_program = int(preset_mode[-1])
            await self.api.async_set_schedule(self.climate_zone_id, heating_program)

        await self.coordinator.async_request_refresh()

    # Number of coordinator polls to wait before giving up on the optimistic override
    _OPTIMISTIC_MODE_TIMEOUT_POLLS = 3

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Clear the optimistic HVAC mode override once the API confirms the new
        state, or after _OPTIMISTIC_MODE_TIMEOUT_POLLS updates if it never does.
        """
        if self._requested_hvac_mode is not None:
            zone_data = self._data
            appliance_data = self.coordinator.get_by_id(self.appliance_id)

            # Check OFF state via zoneMode on the zone
            if zone_data.get("zoneMode") == "FrostProtection":
                actual_mode = HVACMode.OFF
            else:
                # For HEAT/COOL, read operatingMode from the appliance
                operating_mode = appliance_data.get("operatingMode") if appliance_data else None
                actual_mode = OPERATING_MODE_TO_HVAC_MODE.get(operating_mode, HVACMode.OFF)

            if actual_mode == self._requested_hvac_mode:
                self._requested_hvac_mode = None
                self._requested_hvac_mode_polls = 0
            else:
                self._requested_hvac_mode_polls += 1
                if self._requested_hvac_mode_polls >= self._OPTIMISTIC_MODE_TIMEOUT_POLLS:
                    _LOGGER.warning(
                        "Optimistic HVAC mode %s was not confirmed by the API after %d polls; reverting",
                        self._requested_hvac_mode,
                        self._requested_hvac_mode_polls,
                    )
                    self._requested_hvac_mode = None
                    self._requested_hvac_mode_polls = 0

        super()._handle_coordinator_update()
