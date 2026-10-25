# Remeha Home / BAXI HVAC integration for Home Assistant

A fork of [msvisser/remeha_home](https://github.com/msvisser/remeha_home) for BDR Thermea systems (Remeha, BAXI, De Dietrich, Brötje) that are controlled through the Remeha Home cloud. It adds hot water control, heating and cooling control that works with BAXI heat pumps, energy data per producer, schedule and heating curve settings, holiday mode, and push updates.

It is developed and tested on a BAXI Platinum BC iPlus V200 Integra: an air-to-water heat pump with an electric backup heater, two climate zones and a hot water tank. Other appliances on the same cloud should work, but entities depend on what each appliance reports, and only this system has been tested.

You need a working account in the official Remeha Home app (or your brand's version of it). The integration logs in with the same email and password and uses the same cloud API. If the app can't control your system, this integration can't either.

The fork was written with AI assistance and reviewed and tested live on the system above.

## Devices and entities

The integration creates one device per appliance (the heating gateway), one per climate zone and one per hot water zone, named as in the app. Entity IDs follow those names, for example `climate.<zone name>` and `sensor.<appliance name>_water_pressure`.

### Appliance

- Operating mode select: Off, heating and cooling (automatic), or cooling (Off or heating on heat-only appliances). This switches the whole system.
- Sensors: water pressure, outdoor temperature, cloud outdoor temperature (disabled by default), error status, active errors (count, with the raw list as an attribute), thermal mode, operating mode, seasonal mode, holiday start and end (disabled by default).
- Binary sensors: online, water pressure problem, active error, holiday mode.
- Daily energy for the appliance: heating, hot water and cooling, consumed and delivered (disabled by default; these are the consistent figures for the Energy dashboard).
- Daily energy per producer, for example heat pump and backup heater. The totals (heat pump consumed and delivered, backup heater consumed) are enabled by default and show how much the resistive backup heater runs. The heating/hot water/cooling split per producer is disabled by default, because the cloud books it inconsistently (the heat pump's hot water figure includes the backup heater, and the backup heater books hot water as heating).
- Heat pump seasonal efficiency (SCOP), as shown in the app.

Energy values are whole kWh, reset at local midnight, and stay unknown until the gateway's first report of the day, usually within 90 minutes. Producer sensors that aren't reported at startup are added when they appear.

### Climate zone

- Climate entity. HVAC modes: heat, cool and off (off puts only this zone in frost protection). Presets: manual, schedule1, schedule2 and schedule3. HVAC action (heating, cooling, idle) comes from the zone's comfort demand.
- Heating program select (program 1, 2 or 3). Selecting one also puts the zone in schedule mode.
- Pre-heat switch, fireplace mode switch (if supported).
- Heating curve slope and base setpoint numbers, within the limits the API reports.
- Activity temperature numbers: the 5 heating and 5 cooling temperatures the time programs use, named after the activity names set in the app. The cooling ones are disabled by default.
- Sensors: next setpoint and its time, current schedule setpoint, temporary override end time.
- Binary sensors: pre-heat enabled, pre-heat active, heating status (disabled by default).

### Hot water zone

- Water heater entity with the modes Scheduled, Comfort, Eco (anti-frost) and Boost, and target temperatures for Comfort and Eco. Boost can only be started from Scheduled; while it runs, the remaining time is an attribute.
- Sensors: water temperature, boost duration, boost end time, next switch time and activity, status (disabled by default).
- Binary sensors: anti-legionella, heating status and DHW optimisation (both disabled by default).

## Services

- `remeha_home.get_schedule` and `remeha_home.set_schedule` (climate entities) read or replace a time program: `program_type` heating (programs 1-3) or cooling (program 1). Switch points are `{day, time, activity}`. Call `get_schedule` first and edit its output, because the day numbering (0-6) is the API's own.
- `remeha_home.get_hot_water_schedule` and `remeha_home.set_hot_water_schedule` (water heater) do the same for the hot water program, with switch points `{day, time, comfortActive}`.
- `remeha_home.set_holiday` (`start_date`, `end_date`, optional appliance `device_id`) sets holiday mode for whole days. While a holiday is active, the cloud puts every climate zone in frost protection and turns hot water off. Before setting it, the integration saves each zone's mode, program and setpoint, the hot water mode and the appliance operating mode. The saved state survives restarts.
- `remeha_home.clear_holiday` (optional `device_id`) ends the holiday and restores the saved modes. The cloud does not restore them by itself, so the integration also restores them on the first poll after a holiday set from Home Assistant has been cancelled in the app or has ended. A holiday set in the app is not restored, because nothing was saved for it.

## Push updates

Besides polling every 60 seconds, the integration keeps a SignalR connection to the Remeha cloud, as the app does. When the cloud reports a change made in the app, on a thermostat or by the appliance, Home Assistant refreshes within a few seconds. If the push connection drops, updates fall back to polling while it reconnects. The connection state is in the diagnostics download under `push`.

## Things to know

- Any zone mode command (a schedule preset, a program, frost protection) makes the cloud switch an appliance that is Off back on. The climate presets and the program select therefore refuse to act while the appliance is Off; turn it on first. Restoring modes after a holiday does switch an Off appliance on for a few seconds and then back Off.
- Holidays always cover whole local days, and a holiday that includes today starts at once.
- The cloud API doesn't provide flow or return temperatures, live power, compressor state or installer parameters.

## Installation

### HACS

1. In HACS, add `https://github.com/petarlaf/remeha_home_baxi_hvac` as a custom repository of type Integration.
2. Install "Remeha Home" and restart Home Assistant.

If HACS fails to download releases with `Got more than 8190 bytes when reading`, that is a HACS problem with GitHub's current download headers ([hacs/integration#5643](https://github.com/hacs/integration/issues/5643)). Install manually until a fixed HACS version is out.

### Manual

1. Download `remeha_home.zip` from the [latest release](https://github.com/petarlaf/remeha_home_baxi_hvac/releases/latest).
2. Extract it into `custom_components/remeha_home` in your Home Assistant configuration directory.
3. Restart Home Assistant.

Home Assistant 2025.1.4 or newer is required.

## Setup

1. Go to Settings > Devices & services and choose Add integration.
2. Search for Remeha Home.
3. Log in with the email address and password of your Remeha Home app account.

## Diagnostics

Open Settings > Devices & services > Remeha Home and choose Download diagnostics. The file contains the integration version, the entry and coordinator state, the push connection state, the dashboard data, technical details (gateway software and hardware versions), active errors, the latest daily consumption, and the heating curve and activity settings. Passwords, tokens, the account email, the home name, the location and hardware serial numbers are redacted. Appliance and zone IDs are kept so they can be matched to entities.

## Limitations

- The BDR Thermea cloud API is not publicly documented. Payloads were worked out from the app and tested live on one system.
- There are no automated tests in this repository.

## Acknowledgements

Based on the original integration by [msvisser](https://github.com/msvisser/remeha_home).
