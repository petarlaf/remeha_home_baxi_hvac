This is a custom fork of the original remaha home integration - https://github.com/msvisser/remeha_home/tree/main - by msvisser. 

I have a BAXI HVAC system and Hot water boiler - and the original integration didnt' really work for me. I've completely remapped how the climate modes and presets are mapped and set; and how we read the current mode status. I've also created a new hot water entity that now allows you switch between Boost, Eco, Comfort and Scheduled.

All the code is done using AI (as I'm not a developer and I've done this the best I can).

The API documentation requires updating and there are a few tweaks I want to do to the hot water entity. But so far this integration fulfills 99% of my needs.

# Remeha Home integration for Home Assistant
This integration lets you control your Remeha Home thermostats from Home Assistant.

**Before using this integration, make sure you have set up your thermostat in the [Remeha Home](https://play.google.com/store/apps/details?id=com.bdrthermea.application.remeha) app.**
If you are unable to use the Remeha Home app for your thermostat, this integration will not work.

There have been reports by users that this intergration will also work for Baxi, De Dietrich, and Brötje systems (and possibly other BDR Thermea products).
You can simply log in using the credentials that you would use in the respective apps.


### Install manually

1. Install this platform by creating a `custom_components` folder in the same folder as your configuration.yaml, if it doesn't already exist.
2. Create another folder `remeha_home` in the `custom_components` folder. Copy all files from `custom_components/remeha_home` into the `remeha_home` folder.

## Setup
1. In Home Assitant click on `Configuration`
1. Click on `Devices & Services`
1. Click on `+ Add integration`
1. Search for and select `Remeha Home`
1. Enter your email address and password
1. Click "Next"
1. Enjoy


