"""Holiday mode services for Remeha Home.

The cloud keeps holiday dates only (whole local days). While a holiday is
active it puts every climate zone in frost protection and hot water off, and
clearing it does not put them back. So before setting a holiday this module
saves each appliance's zone modes, hot water mode and operating mode, keeps
them in a Store (survives restarts), and restores them when the holiday is
cleared from Home Assistant, cancelled in the app, or ends by itself.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_HOLIDAY = "set_holiday"
SERVICE_CLEAR_HOLIDAY = "clear_holiday"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_DEVICE_ID = "device_id"

STORAGE_KEY = f"{DOMAIN}.holiday"
STORAGE_VERSION = 1
# The read side lags a holiday write by a few seconds; don't treat the
# holiday as ended in that window.
SETTLE_SECONDS = 300
# A zone write switches an Off appliance on; wait before switching it off.
ZONE_WRITE_SETTLE = 5
NO_HOLIDAY = "0001-01-01"

SET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_START_DATE): cv.date,
        vol.Required(ATTR_END_DATE): cv.date,
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)
CLEAR_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
)


def holiday_window(start: date, end: date, tz) -> tuple[str, str]:
    """Return UTC start/end strings that the cloud stores as these local dates."""
    start_local = datetime.combine(start, time(0, 1), tzinfo=tz)
    end_local = datetime.combine(end, time(23, 59), tzinfo=tz)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (
        start_local.astimezone(timezone.utc).strftime(fmt),
        end_local.astimezone(timezone.utc).strftime(fmt),
    )


def holiday_over(holiday: dict | None, today: date) -> bool:
    """Return True when the cloud shows no holiday, or one that has ended."""
    if not holiday:
        return True
    end = str(holiday.get("endTime") or NO_HOLIDAY)
    if end.startswith(NO_HOLIDAY):
        return True
    if holiday.get("active"):
        return False
    try:
        return date.fromisoformat(end[:10]) < today
    except ValueError:
        return False


def take_snapshot(appliance: dict) -> dict[str, Any]:
    """Return the state a holiday changes, for one dashboard appliance."""
    return {
        "operating_mode": appliance.get("operatingMode"),
        "zones": {
            zone["climateZoneId"]: {
                "mode": zone.get("zoneMode"),
                "program": zone.get("activeHeatingClimateTimeProgramNumber") or 1,
                "setpoint": zone.get("setPoint"),
            }
            for zone in appliance.get("climateZones", [])
        },
        "hot_water": {
            zone["hotWaterZoneId"]: zone.get("dhwZoneMode")
            for zone in appliance.get("hotWaterZones", [])
        },
    }


class RemehaHolidayManager:
    """Set and clear holidays and restore what they change."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._snapshots: dict[str, dict] | None = None
        self._lock = asyncio.Lock()

    async def _async_snapshots(self) -> dict[str, dict]:
        if self._snapshots is None:
            self._snapshots = await self._store.async_load() or {}
        return self._snapshots

    async def _async_save(self) -> None:
        await self._store.async_save(self._snapshots or {})

    def _targets(self, call: ServiceCall) -> list[tuple[str, Any]]:
        """Return (appliance_id, entry data) pairs the call is for."""
        device_ids = set(call.data.get(ATTR_DEVICE_ID) or [])
        targets = []
        for data in self.hass.data.get(DOMAIN, {}).values():
            if not isinstance(data, dict) or "coordinator" not in data:
                continue
            coordinator = data["coordinator"]
            for appliance in (coordinator.data or {}).get("appliances", []):
                appliance_id = appliance["applianceId"]
                device_id = coordinator.appliance_device_ids.get(appliance_id)
                if not device_ids or device_id in device_ids:
                    targets.append((appliance_id, data))
        if not targets:
            raise ServiceValidationError("No Remeha appliance matches the target")
        return targets

    @staticmethod
    async def _async_fresh_appliance(data: dict, appliance_id: str) -> dict:
        dashboard = await data["api"].async_get_dashboard()
        for appliance in dashboard.get("appliances", []):
            if appliance["applianceId"] == appliance_id:
                return appliance
        raise HomeAssistantError(f"Appliance {appliance_id} not found")

    async def async_set(self, call: ServiceCall) -> None:
        """Handle remeha_home.set_holiday."""
        start: date = call.data[ATTR_START_DATE]
        end: date = call.data[ATTR_END_DATE]
        if end < start:
            raise ServiceValidationError("end_date must not be before start_date")
        if end < dt_util.now().date():
            raise ServiceValidationError("end_date is in the past")
        start_utc, end_utc = holiday_window(start, end, dt_util.get_default_time_zone())

        async with self._lock:
            snapshots = await self._async_snapshots()
            for appliance_id, data in self._targets(call):
                appliance = await self._async_fresh_appliance(data, appliance_id)
                # A holiday set from HA already keeps its pre-holiday state.
                new_snapshot = False
                if appliance_id in snapshots:
                    pass
                elif not holiday_over(appliance.get("holidaySchedule"), dt_util.now().date()):
                    _LOGGER.warning(
                        "A holiday set outside Home Assistant is already on; zone "
                        "modes will not be restored when it ends"
                    )
                else:
                    snapshots[appliance_id] = take_snapshot(appliance)
                    new_snapshot = True
                if appliance_id in snapshots:
                    snapshots[appliance_id]["set_at"] = dt_util.utcnow().timestamp()
                    snapshots[appliance_id]["end_date"] = end.isoformat()
                await self._async_save()
                try:
                    await data["api"].async_set_holiday(appliance_id, start_utc, end_utc)
                except Exception as err:
                    if new_snapshot:
                        del snapshots[appliance_id]
                        await self._async_save()
                    raise HomeAssistantError(f"Setting the holiday failed: {err}") from err
                await data["coordinator"].async_request_refresh()

    async def async_clear(self, call: ServiceCall) -> None:
        """Handle remeha_home.clear_holiday."""
        async with self._lock:
            for appliance_id, data in self._targets(call):
                past = dt_util.utcnow() - timedelta(days=3)
                fmt = "%Y-%m-%dT%H:%M:%SZ"
                await data["api"].async_set_holiday(
                    appliance_id,
                    past.strftime(fmt),
                    (past + timedelta(days=1)).strftime(fmt),
                )
                await self._async_restore(appliance_id, data)
                await data["coordinator"].async_request_refresh()

    async def _async_restore(self, appliance_id: str, data: dict) -> None:
        """Put back the saved zone, hot water and operating modes, then forget them."""
        snapshots = await self._async_snapshots()
        snapshot = snapshots.get(appliance_id)
        if snapshot is None:
            return
        api = data["api"]
        # Re-send every saved mode: after a holiday a zone can read Scheduling
        # again while keeping the frost setpoint until the mode is re-sent.
        for zone_id, zone in snapshot["zones"].items():
            mode = zone["mode"]
            if mode == "FrostProtection":
                await api.async_set_off(zone_id)
            elif mode == "Manual" and zone.get("setpoint") is not None:
                await api.async_set_manual(zone_id, zone["setpoint"])
            else:
                await api.async_set_schedule(zone_id, int(zone["program"]))
        for zone_id, mode in snapshot["hot_water"].items():
            if mode == "ContinuousComfort":
                await api.async_set_hot_water_comfort(zone_id)
            elif mode == "Off":
                await api.async_set_hot_water_eco(zone_id)
            else:
                await api.async_set_hot_water_schedule(zone_id)
        if snapshot.get("operating_mode") == "Off" and snapshot["zones"]:
            await asyncio.sleep(ZONE_WRITE_SETTLE)
            await api.async_set_operating_mode(appliance_id, "Off")
        del snapshots[appliance_id]
        await self._async_save()
        _LOGGER.info("Restored the pre-holiday modes of appliance %s", appliance_id)

    @callback
    def async_check_ended(self, data: dict) -> None:
        """Coordinator listener: restore once a saved holiday is over."""
        if self._snapshots is None or self._lock.locked():
            return
        coordinator = data["coordinator"]
        today = dt_util.now().date()
        now = dt_util.utcnow().timestamp()
        for appliance in (coordinator.data or {}).get("appliances", []):
            appliance_id = appliance["applianceId"]
            snapshot = self._snapshots.get(appliance_id)
            if snapshot is None or now - snapshot.get("set_at", 0) < SETTLE_SECONDS:
                continue
            if holiday_over(appliance.get("holidaySchedule"), today):
                self.hass.async_create_task(
                    self._async_restore_safely(appliance_id, data),
                    "remeha_home_holiday_restore",
                )

    async def _async_restore_safely(self, appliance_id: str, data: dict) -> None:
        async with self._lock:
            if appliance_id not in (self._snapshots or {}):
                return
            try:
                await self._async_restore(appliance_id, data)
            except Exception as err:  # noqa: BLE001 - retried on the next poll
                _LOGGER.warning("Restoring pre-holiday modes failed: %s", err)
                return
        await data["coordinator"].async_request_refresh()

    async def async_load(self) -> None:
        """Load the saved snapshots so the listener can use them."""
        await self._async_snapshots()


def async_get_manager(hass: HomeAssistant) -> RemehaHolidayManager:
    """Return the shared manager, registering the services the first time."""
    key = f"{DOMAIN}_holiday_manager"
    if (manager := hass.data.get(key)) is None:
        manager = hass.data[key] = RemehaHolidayManager(hass)
        hass.services.async_register(
            DOMAIN, SERVICE_SET_HOLIDAY, manager.async_set, schema=SET_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR_HOLIDAY, manager.async_clear, schema=CLEAR_SCHEMA
        )
    return manager
