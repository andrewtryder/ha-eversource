# Eversource Rates for Home Assistant

[![Validate](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![GitHub release](https://img.shields.io/github/v/release/andrewtryder/ha-eversource)](https://github.com/andrewtryder/ha-eversource/releases)
[![License](https://img.shields.io/github/license/andrewtryder/ha-eversource)](LICENSE)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewtryder&repository=ha-eversource&category=integration)

Unofficial Home Assistant custom integration for public Eversource electricity tariff rates. Version 0.1.x supports **Eversource New Hampshire Residential Rate R** only.

## Features

- Retrieves public, server-rendered Eversource supply and delivery tariff pages about every 12 hours.
- Does not require an Eversource login, account number, API key, or stored credential.
- Uses the public audience-selection cookie `.SEGMENT=nh`; it is not an authenticated account cookie.
- Uses exact `Decimal` arithmetic for supply and delivery tariff components.

## Installation

Add `https://github.com/andrewtryder/ha-eversource` to HACS as a custom repository of type **Integration**, install **Eversource Rates**, and restart Home Assistant. Or copy `custom_components/eversource_rates` to your Home Assistant configuration directory's `custom_components` folder and restart.

## Configuration

Go to **Settings → Devices & services → Add integration**, select **Eversource Rates**, then select **New Hampshire** and **Residential Rate R**. Setup validates public tariff retrieval before creating the entry.

## Entities and Energy Dashboard

- `sensor.eversource_supply_rate` — variable supply price, USD/kWh.
- `sensor.eversource_delivery_rate` — sum of variable delivery riders, USD/kWh.
- `sensor.eversource_total_electricity_rate` — supply plus variable delivery riders, USD/kWh.
- `sensor.eversource_customer_charge` — fixed monthly charge, USD/month.

Delivery components are diagnostic entities disabled by default. To use tariff pricing, go to **Settings → Dashboards → Energy**, edit **Grid consumption**, choose **Use an entity with current price**, and select **Eversource Total Electricity Rate**. Newly published delivery riders are included in the total immediately; their individual diagnostic entity appears after the integration is reloaded.

The total electricity-rate sensor intentionally excludes the fixed customer charge. It is the proper current-price input: supply plus all per-kWh delivery components. The monthly customer charge remains separate and is never smeared across electricity use. Energy Dashboard price changes apply to future calculations; this integration does not retroactively correct past costs.

This release intentionally supports only New Hampshire Residential Rate R. Other territories and rate classes will use dedicated parser strategies when they are added.

## Privacy, data source, and disclaimer

The integration accesses only Eversource's public tariff pages. It does not use browser automation, logged-in sessions, private APIs, or the Sitefinity personalization endpoint. If retrieval or parsing fails, Home Assistant retains prior coordinator data rather than publishing a fabricated rate.

This project is unofficial and is not affiliated with, endorsed by, or sponsored by Eversource.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `PYTHONPATH=. pytest`, `ruff check .`, `ruff format --check .`, and `pre-commit run --all-files`. Release Please owns versions and `CHANGELOG.md`; do not manually create release entries or tags.
