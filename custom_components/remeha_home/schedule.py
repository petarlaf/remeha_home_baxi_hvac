"""Schedule (time program) services for climate zones and hot water zones."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.core import ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform

SERVICE_GET_SCHEDULE = "get_schedule"
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_GET_HOT_WATER_SCHEDULE = "get_hot_water_schedule"
SERVICE_SET_HOT_WATER_SCHEDULE = "set_hot_water_schedule"

ATTR_PROGRAM_TYPE = "program_type"
ATTR_PROGRAM_NUMBER = "program_number"
ATTR_SWITCH_POINTS = "switch_points"

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _time(value) -> str:
    value = str(value)[:5]
    if not TIME_PATTERN.match(value):
        raise vol.Invalid(f"invalid time '{value}', expected HH:MM")
    return value


# Day numbering follows the API (as returned by get_schedule): 0-6.
CLIMATE_SWITCH_POINT_SCHEMA = vol.Schema(
    {
        vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Required("time"): _time,
        vol.Required("activity"): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        vol.Optional("customValue", default=None): vol.Any(None, vol.Coerce(float)),
    }
)

HOT_WATER_SWITCH_POINT_SCHEMA = vol.Schema(
    {
        vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Required("time"): _time,
        vol.Required("comfortActive"): cv.boolean,
    }
)

CLIMATE_PROGRAM_SCHEMA = {
    vol.Optional(ATTR_PROGRAM_TYPE, default="heating"): vol.In(["heating", "cooling"]),
    vol.Optional(ATTR_PROGRAM_NUMBER, default=1): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=3)
    ),
}


def _check_climate_program(program_type: str, program_number: int) -> None:
    if program_type == "cooling" and program_number != 1:
        raise ServiceValidationError("The cooling schedule only has program 1")


def async_register_climate_schedule_services() -> None:
    """Register get/set schedule services on the climate platform."""
    platform = entity_platform.async_get_current_platform()

    async def get_schedule(entity, call) -> ServiceResponse:
        program_type = call.data[ATTR_PROGRAM_TYPE]
        program_number = call.data[ATTR_PROGRAM_NUMBER]
        _check_climate_program(program_type, program_number)
        program = await entity.api.async_get_climate_time_program(
            entity.climate_zone_id, program_type, program_number
        )
        return {
            ATTR_PROGRAM_TYPE: program_type,
            ATTR_PROGRAM_NUMBER: program_number,
            ATTR_SWITCH_POINTS: program.get("switchPoints", []),
        }

    async def set_schedule(entity, call) -> None:
        program_type = call.data[ATTR_PROGRAM_TYPE]
        program_number = call.data[ATTR_PROGRAM_NUMBER]
        _check_climate_program(program_type, program_number)
        await entity.api.async_set_climate_time_program(
            entity.climate_zone_id,
            program_type,
            program_number,
            call.data[ATTR_SWITCH_POINTS],
        )
        await entity.coordinator.async_request_refresh()

    platform.async_register_entity_service(
        SERVICE_GET_SCHEDULE,
        CLIMATE_PROGRAM_SCHEMA,
        get_schedule,
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            **CLIMATE_PROGRAM_SCHEMA,
            vol.Required(ATTR_SWITCH_POINTS): vol.All(
                cv.ensure_list, [CLIMATE_SWITCH_POINT_SCHEMA]
            ),
        },
        set_schedule,
    )


def async_register_hot_water_schedule_services() -> None:
    """Register get/set schedule services on the water heater platform."""
    platform = entity_platform.async_get_current_platform()

    async def get_schedule(entity, call) -> ServiceResponse:
        program = await entity.api.async_get_hot_water_time_program(
            entity.hot_water_zone_id
        )
        return {ATTR_SWITCH_POINTS: program.get("switchPoints", [])}

    async def set_schedule(entity, call) -> None:
        await entity.api.async_set_hot_water_time_program(
            entity.hot_water_zone_id, call.data[ATTR_SWITCH_POINTS]
        )
        await entity.coordinator.async_request_refresh()

    platform.async_register_entity_service(
        SERVICE_GET_HOT_WATER_SCHEDULE,
        {},
        get_schedule,
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_HOT_WATER_SCHEDULE,
        {
            vol.Required(ATTR_SWITCH_POINTS): vol.All(
                cv.ensure_list, [HOT_WATER_SWITCH_POINT_SCHEMA]
            ),
        },
        set_schedule,
    )
