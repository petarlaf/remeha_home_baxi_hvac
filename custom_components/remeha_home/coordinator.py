"""Coordinator for fetching the Remeha Home data."""

import asyncio
import logging
from datetime import timedelta

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .api import RemehaHomeAPI
from .const import DEFAULT_CONSUMPTION_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RemehaHomeUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Home update coordinator."""

    def __init__(self, hass: HomeAssistant, api: RemehaHomeAPI) -> None:
        """Initialize Remeha Home update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.api = api
        self.items = {}
        self.device_info = {}
        self.technical_info = {}
        self.appliance_consumption_data = {}
        self.appliance_last_consumption_data_update = {}

    async def _async_get_technical_info(self, appliance: dict) -> dict:
        """Return cached technical info, falling back to safe defaults."""
        appliance_id = appliance["applianceId"]
        if appliance_id in self.technical_info:
            return self.technical_info[appliance_id]

        try:
            async with asyncio.timeout(15):
                self.technical_info[appliance_id] = (
                    await self.api.async_get_appliance_technical_information(
                        appliance_id
                    )
                )
                _LOGGER.debug(
                    "Requested technical information for appliance %s: %s",
                    appliance_id,
                    self.technical_info[appliance_id],
                )
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed from err
            _LOGGER.warning(
                "Failed to request technical information for appliance %s: %s",
                appliance_id,
                err,
            )
            self.technical_info[appliance_id] = self._default_technical_info(appliance)
        except (TimeoutError, ClientError) as err:
            _LOGGER.warning(
                "Failed to request technical information for appliance %s: %s",
                appliance_id,
                err,
            )
            self.technical_info[appliance_id] = self._default_technical_info(appliance)

        return self.technical_info[appliance_id]

    async def _async_update_consumption_data(
        self, appliance_id: str, now
    ) -> dict | None:
        """Refresh appliance consumption data when due."""
        if appliance_id in self.appliance_last_consumption_data_update and (
            now - self.appliance_last_consumption_data_update[appliance_id]
            < timedelta(minutes=14, seconds=45)
        ):
            return self.appliance_consumption_data.get(appliance_id)

        try:
            async with asyncio.timeout(20):
                consumption_data = (
                    await self.api.async_get_consumption_data_for_today(appliance_id)
                )
            _LOGGER.debug(
                "Requested consumption data for appliance %s: %s",
                appliance_id,
                consumption_data,
            )
            data = consumption_data.get("data") or []
            if data:
                self.appliance_consumption_data[appliance_id] = data[0]
            else:
                _LOGGER.debug(
                    "No consumption data found for appliance %s", appliance_id
                )
                self.appliance_consumption_data.pop(appliance_id, None)

            self.appliance_last_consumption_data_update[appliance_id] = now
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed from err
            _LOGGER.warning(
                "Failed to request consumption data for appliance %s: %s",
                appliance_id,
                err,
            )
        except (TimeoutError, ClientError) as err:
            _LOGGER.warning(
                "Failed to request consumption data for appliance %s: %s",
                appliance_id,
                err,
            )

        return self.appliance_consumption_data.get(appliance_id)

    @staticmethod
    def _default_technical_info(appliance: dict) -> dict:
        """Return safe technical info when the optional endpoint is unavailable."""
        return {
            "applianceName": appliance.get("applianceName") or "Unknown",
            "internetConnectedGateways": [],
        }

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            async with asyncio.timeout(45):
                data = await self.api.async_get_dashboard()
                _LOGGER.debug("Requested dashboard information: %s", data)
        except ClientResponseError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            if err.status == 401:
                raise ConfigEntryAuthFailed from err

            raise UpdateFailed from err
        except (TimeoutError, ClientError) as err:
            raise UpdateFailed from err

        # Save the current time (timezone-aware) for appliance usage data updates
        now = dt_util.now()
        items = {}
        device_info = {}

        for appliance in data.get("appliances", []):
            appliance_id = appliance["applianceId"]
            items[appliance_id] = appliance

            technical_info = await self._async_get_technical_info(appliance)
            consumption_data = await self._async_update_consumption_data(
                appliance_id, now
            )

            # Get the cached consumption data for the appliance or use default values
            appliance["consumptionData"] = (
                consumption_data.copy()
                if consumption_data
                else DEFAULT_CONSUMPTION_DATA.copy()
            )

            device_info[appliance_id] = DeviceInfo(
                identifiers={(DOMAIN, appliance_id)},
                name=(appliance.get("houseName") or "Remeha Home").strip(),
                manufacturer="Remeha",
                model=technical_info.get("applianceName", "Unknown"),
            )

            for climate_zone in appliance.get("climateZones", []):
                climate_zone_id = climate_zone["climateZoneId"]
                # This assumes that all climate zones for an appliance share the same gateway
                gateways = technical_info.get("internetConnectedGateways", [])

                if len(gateways) > 1:
                    _LOGGER.warning(
                        "Appliance %s has more than one gateway, using technical information from the first one",
                        appliance_id,
                    )

                if len(gateways) > 0:
                    gateway_info = gateways[0]
                else:
                    _LOGGER.warning(
                        "Appliance %s has no gateways, using unknown values",
                        appliance_id,
                    )
                    gateway_info = {
                        "name": "Unknown",
                        "hardwareVersion": "Unknown",
                        "softwareVersion": "Unknown",
                    }

                items[climate_zone_id] = climate_zone
                device_info[climate_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, climate_zone_id)},
                    name=(climate_zone.get("name") or "Climate Zone").strip(),
                    manufacturer="Remeha",
                    model=gateway_info["name"],
                    hw_version=gateway_info["hardwareVersion"],
                    sw_version=gateway_info["softwareVersion"],
                    via_device=(DOMAIN, appliance_id),
                )

            for hot_water_zone in appliance.get("hotWaterZones", []):
                hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
                items[hot_water_zone_id] = hot_water_zone
                device_info[hot_water_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, hot_water_zone_id)},
                    name=(hot_water_zone.get("name") or "Hot Water Zone").strip(),
                    manufacturer="Remeha",
                    model="Hot Water Zone",
                    via_device=(DOMAIN, appliance_id),
                )

        self.items = items
        self.device_info = device_info
        return data

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)
