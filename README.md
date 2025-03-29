# Remeha Home / Baxi HVAC Integration for Home Assistant (Custom Fork)

This is a **custom fork** of the original Remeha Home integration by **msvisser** ([msvisser/remeha_home](https://github.com/msvisser/remeha_home)).

This fork was created because the original integration did not fully support the user's **BAXI HVAC system** (heating, cooling) and **Hot Water Boiler**.

## Key Changes in this Fork

*   **Climate Entity (`climate.remeha_home`)**:
    *   Remapped HVAC modes: `HEAT` (`AutomaticCoolingHeating`), `COOL` (`ForcedCooling`), `OFF` (`FrostProtection`).
    *   Remapped Preset modes: `manual`, `schedule1`, `schedule2`, `schedule3`. Control logic adjusted for these modes.
    *   Improved HVAC Action detection based on the API's `activeComfortDemand` status (`ProducingHeat`, `Idle`, `ProducingCold`).
*   **Water Heater Entity (`water_heater.remeha_home`)**:
    *   Introduced full support for hot water control.
    *   Supports operation modes: `Scheduled`, `Comfort`, `Eco` (Anti-Frost), and `Boost`.
    *   Allows setting target temperatures specifically for `Comfort` and `Eco` modes.
    *   `Boost` mode can only be activated when the system is in `Scheduled` mode (matching app behavior) and displays remaining boost time.

**Note:** The development of this fork was assisted by AI, as the author is not a developer. While functional for the author's needs, further refinements or bug fixes might be required.

---

## Original Integration Information

This integration lets you control your Remeha Home thermostats (and compatible BDR Thermea brands) from Home Assistant.

**Before using this integration, make sure you have set up your thermostat in the [Remeha Home app](https://play.google.com/store/apps/details?id=com.bdrthermea.application.remeha) (or the equivalent app for your brand).** If you cannot use the official app, this integration will likely not work.

It has been reported that this integration may also work for **Baxi**, **De Dietrich**, and **Brötje** systems. You can log in using the same credentials you use for your brand's specific app.

## Provided Entities

This integration creates the following entities:

*   **Climate:** Controls the main heating/cooling zone.
    *   Allows setting target temperature.
    *   Supports HVAC Modes: Heat, Cool, Off.
    *   Supports Preset Modes: Manual, Schedule1, Schedule2, Schedule3.
*   **Water Heater:** Controls the domestic hot water zone.
    *   Allows setting target temperature (in Comfort/Eco modes).
    *   Supports Operation Modes: Scheduled, Comfort, Eco, Boost.
    *   Displays current water temperature.
*   **Sensors:** Various sensors providing information like:
    *   Room Temperature
    *   Outdoor Temperature
    *   Water Pressure
    *   Energy Consumption (Heating, Hot Water, Cooling - updated approx. every 15 mins)
*   **Binary Sensors:** Indicate status like:
    *   Frost Protection Active
    *   Heating Status
    *   Hot Water Status
*   **Switches:** May include switches for specific functions if applicable to your system (e.g., enabling/disabling certain modes - check your specific device).

## Installation

### HACS (Recommended)

1.  Add this repository as a custom repository in HACS (Home Assistant Community Store).
2.  Search for "Remeha Home Baxi HVAC" and install the integration.
3.  Restart Home Assistant.

### Manual Installation

1.  Ensure the `custom_components` folder exists in your Home Assistant configuration directory.
2.  Copy the `custom_components/remeha_home` folder from this repository into your `custom_components` directory.
3.  Restart Home Assistant.

## Setup

1.  In Home Assistant, go to `Settings` > `Devices & Services`.
2.  Click `+ Add Integration`.
3.  Search for and select `Remeha Home`.
4.  Enter the email address and password you use for your Remeha/Baxi/etc. mobile app.
5.  Click "Submit".
6.  The integration will discover your devices and add the corresponding entities.

## Known Issues / Future Work

*   The underlying API interactions are complex and not fully documented publicly.
*   Error handling for API edge cases could potentially be improved.
*   No automated tests are included in this fork.
*   Minor tweaks to the water heater entity might still be desired.

## Acknowledgements

*   Based on the work of **msvisser** ([msvisser/remeha_home](https://github.com/msvisser/remeha_home)).
