# Remeha Home / Baxi HVAC Integration for Home Assistant (Custom Fork)

This is a **custom fork** of the original Remeha Home integration by **msvisser** ([msvisser/remeha_home](https://github.com/msvisser/remeha_home)).

This fork was created primarily to:
1.  Provide **full Hot Water control** for BDR Thermea systems, a feature **missing** in the original integration.
2.  Adapt the **Climate control** logic to work more reliably with the author's specific **BAXI HVAC system** (Heating & Cooling).

**Testing:** This fork has been developed and tested specifically on a **Baxi PLATINUM BC IPLUS V200 INTEGRA** system. While it may work on other Baxi or BDR Thermea models, compatibility is not guaranteed.

---

## Key Improvements & Differences from Original (`msvisser/remeha_home`)

*   **⭐ New Water Heater Entity (`water_heater.remeha_home`):**
    *   Provides full control over Domestic Hot Water (DHW) zones.
    *   Supports Operation Modes: `Scheduled`, `Comfort`, `Eco` (Anti-Frost), and `Boost`.
    *   Allows setting target temperatures specifically for `Comfort` and `Eco` modes via dedicated API calls.
    *   `Boost` mode correctly implemented (only available from `Scheduled` mode) and displays remaining boost time as a state attribute.
    *   *(The original integration only offered a temperature sensor for hot water).*
*   **Climate Entity Enhancements (`climate.remeha_home`):**
    *   Reworked `HVACMode` mapping for better Baxi compatibility: `HEAT` (`AutomaticCoolingHeating`), `COOL` (`ForcedCooling`), `OFF` (`FrostProtection`).
    *   Simplified `PresetMode` handling: `manual`, `schedule1`, `schedule2`, `schedule3` directly trigger corresponding API modes.
    *   Improved `HVACAction` detection (`Heating`, `Cooling`, `Idle`) based on the API's `activeComfortDemand` status.
*   **⭐ New Energy Consumption Sensors:**
    *   Added sensors for daily energy consumed/delivered for Heating, Hot Water, and Cooling (where applicable). Data is fetched periodically (approx. every 15 mins).
*   **Enhanced Data Fetching:**
    *   The integration now retrieves appliance technical details (model name, gateway versions) and energy consumption data from the API.
*   **API Client:**
    *   Added new API functions to support all the features above.
    *   Includes specific error handling for known API quirks (e.g., 400 error on token refresh).

**Note:** The development of this fork was assisted by AI, as the author is not a developer. While functional for the author's tested model, further refinements or bug fixes might be required for broader compatibility.

---

## General Information (Applies to Fork)

This integration lets you control your Remeha Home thermostats (and compatible BDR Thermea brands like Baxi, De Dietrich, Brötje) from Home Assistant.

**Prerequisite:** You **must** be able to set up and control your thermostat using the official [Remeha Home app](https://play.google.com/store/apps/details?id=com.bdrthermea.application.remeha) (or the equivalent app for your brand: Baxi, De Dietrich, etc.). If the official app doesn't work for your system, this integration will likely not work either. Log in using the same credentials as your official app.

## Provided Entities (This Fork)

This integration aims to create the following entities based on your system's capabilities:

*   **Climate (`climate.remeha_home`):** Controls the main heating/cooling zone.
    *   Status: Current Temp, Target Temp, HVAC Action (Heating/Cooling/Idle)
    *   Controls: HVAC Mode (Heat, Cool, Off), Preset Mode (Manual, Schedule 1/2/3), Target Temperature.
*   **Water Heater (`water_heater.remeha_home`):** Controls the domestic hot water zone.
    *   Status: Current Temp, Target Temp (varies by mode), Current Operation Mode.
    *   Controls: Operation Mode (Scheduled, Comfort, Eco, Boost), Target Temperature (in Comfort/Eco modes).
    *   Attributes: Remaining Boost Time (when active).
*   **Sensors (`sensor.*`):**
    *   Outdoor Temperature (Appliance, if available)
    *   Cloud Outdoor Temperature (Appliance, disabled by default)
    *   Water Pressure (Appliance, if available)
    *   Heating Energy Consumed/Delivered (Appliance, Daily, disabled by default)
    *   Hot Water Energy Consumed/Delivered (Appliance, Daily, disabled by default)
    *   Cooling Energy Consumed/Delivered (Appliance, Daily, disabled by default)
    *   Error Status (Appliance)
    *   Next Schedule Setpoint & Time (Climate Zone)
    *   Current Schedule Setpoint (Climate Zone)
    *   Water Temperature (Hot Water Zone)
    *   Hot Water Status (Hot Water Zone, disabled by default)
    *   Boost Mode End Time (Hot Water Zone)
*   **Binary Sensors (`binary_sensor.*`):**
    *   Climate Zone Heating Status (based on comfort demand)
    *   Hot Water Zone Heating Status
    *   Online, Water Pressure Problem, Active Error, Holiday Mode (Appliance)
    *   Pre-heat Enabled / Active (Climate Zone)
    *   Anti-Legionella, DHW Optimization (Hot Water Zone, the latter disabled by default)
*   **More sensors (`sensor.*`):**
    *   Active Errors (Appliance): number of active faults, with the raw list from the API as an attribute
    *   Thermal Mode, Operating Mode, Seasonal Mode (Appliance)
    *   Per-producer daily energy, e.g. Heat Pump and Backup Heater consumed/delivered. The totals (heat pump consumed and delivered, backup heater consumed) are enabled by default and suit the Energy dashboard as individual devices; the backup heater total shows how much the resistive heater runs. The per-use split (heating, hot water, cooling) is created disabled because the cloud attributes it inconsistently: the heat pump's hot water figures include the backup heater, and the backup heater books hot water as heating. Values are whole kWh, reset at local midnight, and stay unknown until the gateway's first report of the day (usually within 90 minutes). Sensors for a producer that isn't reported at startup are added once it appears.
    *   Heat Pump Seasonal Efficiency (SCOP), as shown in the app
    *   Holiday Start / End (Appliance, disabled by default)
    *   Temporary Override End Time (Climate Zone)
    *   Next Switch Time / Activity (Hot Water Zone)
*   **Numbers (`number.*`, configuration):**
    *   Heating Curve Slope and Base Setpoint (per Climate Zone), with the limits reported by the API
    *   Schedule activity temperatures (per Climate Zone): the 5 heating and 5 cooling presets the time programs use. Custom activity names from the app are used as entity names.
*   **Select (`select.*`):**
    *   Operating Mode (Appliance): Off, Heating and cooling (automatic) or Cooling (Off or Heating on heat-only appliances). This switches the whole system; turning a climate entity off only puts that zone in frost protection.
*   **Switches (`switch.*`):**
    *   Fireplace Mode (Climate - if supported)

### Notes

*   Any zone mode command (such as choosing a schedule preset) makes the cloud switch an appliance that is Off back on. The climate entity therefore refuses preset changes while the appliance is Off; turn it on first.

### Services

*   `remeha_home.get_schedule` / `remeha_home.set_schedule` (climate entities): read or replace a time program (`program_type` heating 1-3 or cooling 1). Switch points are `{day, time, activity}`; call `get_schedule` first and edit its output, since the day numbering is the API's own (0-6).
*   `remeha_home.get_hot_water_schedule` / `remeha_home.set_hot_water_schedule` (water heater): the same for the hot water program, with switch points `{day, time, comfortActive}`.

*(Availability of some sensors/switches depends on your specific appliance model and configuration)*

## Installation

### HACS (Recommended)

1.  Add this repository URL (`https://github.com/petarlaf/remeha_home_baxi_hvac`) as a custom repository in HACS (Integration type).
2.  Search for "Remeha Home Baxi HVAC" (or similar) under Integrations and install it.
3.  Restart Home Assistant.

### Manual Installation

1.  Ensure the `custom_components` folder exists in your Home Assistant configuration directory (where `configuration.yaml` is).
2.  Copy the complete `custom_components/remeha_home` folder from this repository into your `custom_components` directory.
3.  Restart Home Assistant.

## Setup

1.  In Home Assistant, go to `Settings` > `Devices & Services`.
2.  Click `+ Add Integration`.
3.  Search for and select `Remeha Home`.
4.  Enter the email address and password you use for your Remeha/Baxi/etc. mobile app.
5.  Click "Submit".
6.  The integration will discover your devices and add the corresponding entities.

## Diagnostics

Open `Settings` > `Devices & Services` > `Remeha Home` and choose `Download diagnostics`. The file contains the integration version, the entry and coordinator state, the dashboard, technical details (gateway software and hardware versions), active errors, the latest daily consumption and the heating curve and activity settings. Passwords, tokens, your account email, the home name, location and hardware serial numbers are redacted before the file is created. Appliance and zone IDs are kept so they can be matched to entities.

## Known Issues / Future Work

*   The underlying BDR Thermea API is not publicly documented.
*   Error handling for less common API responses could potentially be improved.
*   No automated tests are included in this fork.

## Acknowledgements

*   Based heavily on the original work of **msvisser** ([msvisser/remeha_home](https://github.com/msvisser/remeha_home)).
