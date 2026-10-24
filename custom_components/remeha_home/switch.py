"""Platform for switch integration."""

from __future__ import annotations
import logging


from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    """Set up the Remeha Home switch entities from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]

            entities.append(
                RemehaHomeFireplaceModeSwitch(api, coordinator, climate_zone_id)
            )
            entities.append(
                RemehaHomePreheatSwitch(
                    api, coordinator, appliance["applianceId"], climate_zone_id
                )
            )

    async_add_entities(entities)


class RemehaHomeSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Create a Remeha Home switch entity."""
        super().__init__(coordinator)
        self.api = api
        self.climate_zone_id = climate_zone_id
        self.entity_description = entity_description

        self._attr_unique_id = "_".join(
            [DOMAIN, self.climate_zone_id, entity_description.key]
        )

    @property
    def _data(self):
        """Return the climate zone data for this switch."""
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._data is not None

    @property
    def is_on(self) -> bool | None:
        """Return the state of this switch."""
        data = self._data
        if data is None:
            return None
        return data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)


class RemehaHomeFireplaceModeSwitch(RemehaHomeSwitch):
    """Representation of a fireplace mode switch."""

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
    ) -> None:
        """Create a Remeha Home fireplace mode switch entity."""
        super().__init__(
            api,
            coordinator,
            climate_zone_id,
            SwitchEntityDescription(
                key="firePlaceModeActive",
                name="Fireplace Mode",
                device_class=SwitchDeviceClass.SWITCH,
            ),
        )

    @property
    def icon(self):
        """Return the icon for this switch."""
        if self.is_on:
            return "mdi:fireplace"
        return "mdi:fireplace-off"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        _LOGGER.debug("Enable fireplace mode")
        await self.api.async_set_fireplace_mode(self.climate_zone_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        _LOGGER.debug("Disable fireplace mode")
        await self.api.async_set_fireplace_mode(self.climate_zone_id, False)
        await self.coordinator.async_request_refresh()


class RemehaHomePreheatSwitch(RemehaHomeSwitch):
    """Pre-heat of a climate zone.

    The cloud only accepts pre-heat for all climate zones of an appliance in one
    request, so this sends the current state of the other zones unchanged.
    """

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        climate_zone_id: str,
    ) -> None:
        """Create a Remeha Home pre-heat switch entity."""
        super().__init__(
            api,
            coordinator,
            climate_zone_id,
            SwitchEntityDescription(
                key="preHeat",
                name="Pre-heat",
                icon="mdi:clock-start",
            ),
        )
        self.appliance_id = appliance_id

    @property
    def is_on(self) -> bool | None:
        """Return the pre-heat state of this climate zone."""
        data = self._data
        if data is None:
            return None
        return (data.get("preHeat") or {}).get("enabled")

    async def _async_set_preheat(self, enabled: bool) -> None:
        """Write pre-heat for this zone and keep every other zone as it is."""
        appliance = self.coordinator.get_by_id(self.appliance_id) or {}
        enabled_by_zone: dict[str, bool] = {}
        for zone in appliance.get("climateZones", []):
            zone_id = zone["climateZoneId"]
            if zone_id == self.climate_zone_id:
                enabled_by_zone[zone_id] = enabled
                continue
            current = (zone.get("preHeat") or {}).get("enabled")
            if current is None:
                raise HomeAssistantError(
                    "Pre-heat state of the other climate zones is unknown; "
                    "try again after the next data refresh."
                )
            enabled_by_zone[zone_id] = current

        await self.api.async_set_preheat(self.appliance_id, enabled_by_zone)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn pre-heat on for this climate zone."""
        _LOGGER.debug("Enable pre-heat for climate zone %s", self.climate_zone_id)
        await self._async_set_preheat(True)

    async def async_turn_off(self, **kwargs):
        """Turn pre-heat off for this climate zone."""
        _LOGGER.debug("Disable pre-heat for climate zone %s", self.climate_zone_id)
        await self._async_set_preheat(False)
