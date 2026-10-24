"""Platform for select integration (appliance operating mode)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Select option -> API operatingMode value
OPERATING_MODE_OPTIONS = {
    "off": "Off",
    "automatic_heating": "AutomaticHeating",
    "automatic_cooling_heating": "AutomaticCoolingHeating",
    "forced_cooling": "ForcedCooling",
}
API_TO_OPTION = {value: key for key, value in OPERATING_MODE_OPTIONS.items()}

# Heating time programs 1-3 of a climate zone (option = program number)
HEATING_PROGRAM_OPTIONS = ["1", "2", "3"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home select entities from a config entry."""
    api: RemehaHomeAPI = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: RemehaHomeUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[SelectEntity] = [
        RemehaHomeOperatingModeSelect(api, coordinator, appliance["applianceId"])
        for appliance in coordinator.data["appliances"]
    ]
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance.get("climateZones", []):
            entities.append(
                RemehaHomeHeatingProgramSelect(
                    api,
                    coordinator,
                    appliance["applianceId"],
                    climate_zone["climateZoneId"],
                )
            )

    async_add_entities(entities)


class RemehaHomeOperatingModeSelect(CoordinatorEntity, SelectEntity):
    """Appliance-wide operating mode: off, heating, heating/cooling, cooling.

    This switches the whole system; the per-zone climate entities only put a
    zone in frost protection when turned off.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "operating_mode"
    _attr_icon = "mdi:heat-pump-outline"

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
    ) -> None:
        """Create the operating mode select."""
        super().__init__(coordinator)
        self.api = api
        self.appliance_id = appliance_id
        self._attr_unique_id = f"{DOMAIN}_{appliance_id}_operatingMode_select"

    @property
    def _data(self) -> dict | None:
        return self.coordinator.get_by_id(self.appliance_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._data is not None

    @property
    def options(self) -> list[str]:
        """Return the modes this appliance supports, plus the current one."""
        data = self._data or {}
        if data.get("capabilityCooling"):
            options = ["off", "automatic_cooling_heating", "forced_cooling"]
        else:
            options = ["off", "automatic_heating"]
        current = self.current_option
        if current is not None and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current operating mode."""
        mode = (self._data or {}).get("operatingMode")
        if mode is None:
            return None
        if mode not in API_TO_OPTION:
            _LOGGER.debug("Unknown operating mode reported by the API: %s", mode)
            return None
        return API_TO_OPTION[mode]

    @property
    def extra_state_attributes(self) -> dict:
        """Return the raw API value for unknown modes and automations."""
        return {"api_operating_mode": (self._data or {}).get("operatingMode")}

    async def async_select_option(self, option: str) -> None:
        """Change the appliance operating mode."""
        mode = OPERATING_MODE_OPTIONS[option]
        _LOGGER.debug("Setting appliance %s operating mode to %s", self.appliance_id, mode)
        await self.api.async_set_operating_mode(self.appliance_id, mode)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.appliance_id)


class RemehaHomeHeatingProgramSelect(CoordinatorEntity, SelectEntity):
    """Heating time program (1-3) a climate zone follows.

    Selecting a program calls the same schedule endpoint as the Schedule 1/2/3
    presets, so it also switches the zone into schedule mode. Like the presets,
    it is refused while the appliance is Off, because the cloud would switch the
    whole appliance back on.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "heating_program"
    _attr_icon = "mdi:calendar-clock"
    _attr_options = HEATING_PROGRAM_OPTIONS

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        climate_zone_id: str,
    ) -> None:
        """Create the heating program select for a climate zone."""
        super().__init__(coordinator)
        self.api = api
        self.appliance_id = appliance_id
        self.climate_zone_id = climate_zone_id
        self._attr_unique_id = f"{DOMAIN}_{climate_zone_id}_heating_program_select"

    @property
    def _data(self) -> dict | None:
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._data is not None

    @property
    def current_option(self) -> str | None:
        """Return the heating program the API reports as active."""
        program = (self._data or {}).get("activeHeatingClimateTimeProgramNumber")
        if program in (1, 2, 3):
            return str(program)
        return None

    async def async_select_option(self, option: str) -> None:
        """Switch the climate zone to the heating program."""
        appliance_data = self.coordinator.get_by_id(self.appliance_id) or {}
        if appliance_data.get("operatingMode") == "Off":
            raise ServiceValidationError(
                "The appliance is switched off. Turn it on first (climate turn on "
                "or the Operating Mode select), then choose a heating program; "
                "changing the program now would switch the whole system on."
            )

        _LOGGER.debug(
            "Setting climate zone %s to heating program %s",
            self.climate_zone_id,
            option,
        )
        await self.api.async_set_schedule(self.climate_zone_id, int(option))
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)
