"""Constants for the Remeha Home integration."""

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPressure,
    UnitOfTemperature,
)

DOMAIN = "remeha_home"

# Shared API subscription key (public key embedded in the official app)
API_SUBSCRIPTION_KEY = "df605c5470d846fc91e848b1cc653ddf"

DEFAULT_CONSUMPTION_DATA = {
    "heatingEnergyConsumed": None,
    "hotWaterEnergyConsumed": None,
    "coolingEnergyConsumed": None,
    "heatingEnergyDelivered": None,
    "hotWaterEnergyDelivered": None,
    "coolingEnergyDelivered": None,
}

APPLIANCE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="waterPressure",
        name="Water Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoorTemperatureInformation.applianceOutdoorTemperature",
        name="Outdoor Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoorTemperatureInformation.cloudOutdoorTemperature",
        name="Cloud Outdoor Temperature",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="consumptionData.heatingEnergyConsumed",
        name="Heating Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.hotWaterEnergyConsumed",
        name="Hot Water Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.coolingEnergyConsumed",
        name="Cooling Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.heatingEnergyDelivered",
        name="Heating Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.hotWaterEnergyDelivered",
        name="Hot Water Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.coolingEnergyDelivered",
        name="Cooling Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="errorStatus",
        name="Error Status",
        icon="mdi:alert-circle",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="activeThermalMode",
        name="Thermal Mode",
        icon="mdi:heat-pump-outline",
    ),
    SensorEntityDescription(
        key="operatingMode",
        name="Operating Mode",
        icon="mdi:cog-outline",
    ),
    SensorEntityDescription(
        key="seasonalMode",
        name="Seasonal Mode",
        icon="mdi:weather-partly-snowy",
    ),
    SensorEntityDescription(
        key="holidaySchedule.startTime",
        name="Holiday Start",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="holidaySchedule.endTime",
        name="Holiday End",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
]

# Sensor for the list returned by /appliances/{id}/activeerrors. The state is
# the number of active errors; the raw list is exposed as an attribute.
ACTIVE_ERRORS_SENSOR_TYPE = SensorEntityDescription(
    key="activeErrors",
    name="Active Errors",
    icon="mdi:alert-circle-check-outline",
    state_class=SensorStateClass.MEASUREMENT,
)

# Display names for the producer types found in producerPerformanceStatistics.
PRODUCER_TYPE_NAMES = {
    "HeatPumpAirSource": "Heat Pump",
    "HeatPumpGroundSource": "Heat Pump",
    "ElectricBackup": "Backup Heater",
    "GasBoiler": "Boiler",
}

# Per-producer statistics from the daily energy consumption endpoint. Energy
# values are today's totals in whole kWh and reset at midnight;
# seasonalEfficiency is the seasonal COP the app shows and is not a daily value.
#
# Only the producer totals are reliable: the producers' totals add up to the
# appliance's consumption, and the heat pump's delivered total plus the backup
# heater's consumption add up to the appliance's delivered energy. The split
# per use is not: the heat pump's hot water figures include the backup heater
# (often more than the heat pump's own total), and the backup heater books its
# hot water energy as heating. Those sensors are created disabled.
PRODUCER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="energyConsumptionCH",
        name="Heating Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionDHW",
        name="Hot Water Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionCooling",
        name="Cooling Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionTotal",
        name="Total Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionCH",
        name="Heating Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionDHW",
        name="Hot Water Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionCooling",
        name="Cooling Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionTotal",
        name="Total Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="seasonalEfficiency",
        name="Seasonal Efficiency (SCOP)",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]

# Producer sensors enabled by default; the rest are created disabled.
PRODUCER_SENSORS_ENABLED_BY_DEFAULT = {
    "HeatPumpAirSource": {
        "energyConsumptionTotal",
        "energyProductionTotal",
        "seasonalEfficiency",
    },
    "HeatPumpGroundSource": {
        "energyConsumptionTotal",
        "energyProductionTotal",
        "seasonalEfficiency",
    },
    "ElectricBackup": {"energyConsumptionTotal"},
}

CLIMATE_ZONE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="nextSetpoint",
        name="Next Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="nextSwitchTime",
        name="Next Setpoint Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="currentScheduleSetPoint",
        name="Current Schedule Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temporaryOverride.endTime",
        name="Temporary Override End Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

HOT_WATER_ZONE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="dhwTemperature",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dhwStatus",
        name="Status",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="boostModeEndTime",
        name="Boost Mode End Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="nextSwitchTime",
        name="Next Switch Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="nextSwitchActivity",
        name="Next Switch Activity",
        icon="mdi:calendar-clock",
    ),
]

APPLIANCE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="applianceOnline",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        bool,
    ),
    (
        BinarySensorEntityDescription(
            key="waterPressureOK",
            name="Water Pressure Problem",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
        lambda value: not value,
    ),
    (
        BinarySensorEntityDescription(
            key="activeErrors",
            name="Active Error",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
        lambda value: len(value) > 0,
    ),
    (
        BinarySensorEntityDescription(
            key="holidaySchedule.active",
            name="Holiday Mode",
            icon="mdi:palm-tree",
        ),
        bool,
    ),
]

CLIMATE_ZONE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="activeComfortDemand",
            name="Status",
            entity_registry_enabled_default=False,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda value: value in ["ProducingHeat", "RequestingHeat"],
    ),
    (
        BinarySensorEntityDescription(
            key="preHeat.enabled",
            name="Pre-heat Enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        bool,
    ),
    (
        BinarySensorEntityDescription(
            key="preHeat.active",
            name="Pre-heat Active",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        bool,
    ),
]

HOT_WATER_ZONE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="dhwStatus",
            name="Status",
            entity_registry_enabled_default=False,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda value: value == "ProducingHeat",
    ),
    (
        BinarySensorEntityDescription(
            key="antiLegionellaEnabled",
            name="Anti-Legionella",
            icon="mdi:bacteria-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        bool,
    ),
    (
        BinarySensorEntityDescription(
            key="optimizationEnabled",
            name="DHW Optimization",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        bool,
    ),
]
