"""Diagnostics support for the Remeha Home integration.

The download contains the integration version, the config entry, the
coordinator state and the cached API data (dashboard, technical details,
active errors, daily consumption, heating curves and activities).

Credentials, the account identity, the home name, location, hardware serial
numbers and device indexes are redacted. Appliance and climate zone GUIDs are
kept because they are needed to match entities to the API while debugging.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.loader import async_get_integration

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# Key names redacted wherever they occur (exact match).
TO_REDACT = {
    # Credentials and tokens
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "password",
    "email",
    "username",
    # Account identity
    "userId",
    "accountId",
    # Location and home identity
    "latitude",
    "longitude",
    "lat",
    "lon",
    "location",
    "address",
    "postalCode",
    "zipCode",
    "houseName",
    # Hardware identifiers
    "gatewaySerial",
    "serialNumber",
    "deviceIndex",
}

# Any key containing one of these fragments (case-insensitive) is redacted too,
# so variants such as "userEmail" or "gatewaySerialNo" do not leak.
SENSITIVE_KEY_FRAGMENTS = ("serial", "email", "password", "secret", "token")

# Keys the coordinator adds to the dashboard appliances and climate zones. They
# are reported in their own sections, so they are removed from the dashboard copy.
INJECTED_APPLIANCE_KEYS = ("consumptionData", "producers", "activeErrors")
INJECTED_ZONE_KEYS = ("heatingCurve", "activities")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Remeha Home config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    result: dict[str, Any] = {
        "integration": {
            "domain": DOMAIN,
            "version": str(integration.version) if integration.version else None,
        },
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
    if coordinator is None:
        result["loaded"] = False
        return _redact(result)

    result["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "last_update_success_time": _iso(
            getattr(coordinator, "last_update_success_time", None)
        ),
        "last_exception": (
            str(coordinator.last_exception) if coordinator.last_exception else None
        ),
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
    }
    result["dashboard"] = _dashboard_snapshot(coordinator.data)
    result["technical_details"] = coordinator.technical_info
    result["active_errors"] = coordinator.appliance_active_errors
    result["latest_consumption"] = coordinator.appliance_consumption_data
    result["zone_settings"] = {
        zone_id: {
            **settings,
            "last_fetched": _iso(
                coordinator.zone_settings_last_update.get(zone_id)
            ),
        }
        for zone_id, settings in coordinator.zone_settings.items()
    }

    return _redact(result)


def _dashboard_snapshot(dashboard: dict | None) -> dict | None:
    """Return a copy of the dashboard without the coordinator-injected keys."""
    if dashboard is None:
        return None
    snapshot = deepcopy(dashboard)
    for appliance in snapshot.get("appliances") or []:
        for key in INJECTED_APPLIANCE_KEYS:
            appliance.pop(key, None)
        for zone in appliance.get("climateZones") or []:
            for key in INJECTED_ZONE_KEYS:
                zone.pop(key, None)
    return snapshot


def _iso(value: Any) -> Any:
    """Return ISO 8601 text for datetimes so the result is JSON serialisable."""
    return value.isoformat() if isinstance(value, datetime) else value


def _redact(data: Any) -> Any:
    """Redact by known key names, then by sensitive key fragments."""
    return _redact_fragments(async_redact_data(data, TO_REDACT))


def _redact_fragments(data: Any) -> Any:
    """Recursively redact values whose key contains a sensitive fragment."""
    if isinstance(data, dict):
        return {
            key: (
                REDACTED
                if value is not None and _is_sensitive_key(key)
                else _redact_fragments(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_redact_fragments(item) for item in data]
    return data


def _is_sensitive_key(key: Any) -> bool:
    """Return True if a key name contains a sensitive fragment."""
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)
