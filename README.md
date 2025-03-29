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
    *   Room Temperature
    *   Outdoor Temperature (if available)
    *   Water Pressure (if available)
    *   Heating Energy Consumed/Delivered (Daily)
    *   Hot Water Energy Consumed/Delivered (Daily)
    *   Cooling Energy Consumed/Delivered (Daily)
    *   Next Schedule Setpoint & Time (Climate)
*   **Binary Sensors (`binary_sensor.*`):**
    *   Frost Protection Active (Climate)
    *   Heating Status (Appliance)
    *   Hot Water Status (Appliance)
*   **Switches (`switch.*`):**
    *   Fireplace Mode (Climate - if supported)

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

## Known Issues / Future Work

*   The underlying BDR Thermea API is not publicly documented.
*   Error handling for less common API responses could potentially be improved.
*   No automated tests are included in this fork.

## Acknowledgements

*   Based heavily on the original work of **msvisser** ([msvisser/remeha_home](https://github.com/msvisser/remeha_home)).
