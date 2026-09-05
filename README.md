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
- Exposes an all-in variable electricity-rate sensor intended for Home Assistant's Energy dashboard.
- Keeps the fixed monthly customer charge separate from the per-kWh price.

## Supported tariffs

Version 0.1.x intentionally supports only:

- **Service territory:** New Hampshire
- **Rate class:** Residential Rate R
- **Supply:** Eversource default service

Other Eversource territories and rate classes require separately verified public tariff sources and parser strategies before they can be enabled.

## Installation

Add `https://github.com/andrewtryder/ha-eversource` to HACS as a custom repository of type **Integration**, install **Eversource Rates**, and restart Home Assistant.

For a manual installation, copy `custom_components/eversource_rates` to your Home Assistant configuration directory's `custom_components` folder and restart Home Assistant.

## Configuration

Go to **Settings → Devices & services → Add integration**, select **Eversource Rates**, then select **New Hampshire** and **Residential Rate R**. Setup validates public tariff retrieval before creating the entry.

## Entities

| Entity | Meaning | Intended use |
| --- | --- | --- |
| `sensor.eversource_supply_rate` | Eversource supply price in USD/kWh | Reference / diagnostics |
| `sensor.eversource_delivery_rate` | Sum of variable Eversource delivery charges in USD/kWh | Reference / diagnostics |
| `sensor.eversource_total_electricity_rate` | Supply + all variable delivery charges in USD/kWh | **Home Assistant Energy dashboard current price** |
| `sensor.eversource_customer_charge` | Fixed monthly customer charge | Reference only; do not use as a per-kWh price |

Individual delivery components are also available as diagnostic entities and are disabled by default. Newly published delivery riders are included in the total rate immediately after a successful refresh; a newly discovered rider's individual diagnostic entity appears after the integration is reloaded.

## Using Eversource Rates with the Home Assistant Energy dashboard

This integration provides the **price of electricity**, not your home's electricity-consumption measurement. Home Assistant still needs a separate cumulative energy sensor that records how many kWh you import from the grid. That sensor can come from a smart meter, whole-home energy monitor, inverter, ESPHome device, Shelly, Emporia, utility-meter integration, or another compatible source.

### 1. Confirm you have a grid-consumption sensor

Before configuring pricing, make sure Home Assistant has a suitable grid-import energy sensor. It should normally:

- report cumulative energy rather than instantaneous power;
- use an energy unit such as `kWh`;
- be accepted by Home Assistant as a grid-consumption source in the Energy dashboard; and
- be recorded by Home Assistant's Recorder so long-term statistics can be generated.

A sensor reporting watts (`W`) or kilowatts (`kW`) is a **power** sensor and cannot be used directly as cumulative grid energy without first converting/integrating it to energy.

### 2. Add or edit grid consumption

1. Open **Settings → Dashboards → Energy**.
2. Under **Electricity grid**, add a grid-consumption source or edit your existing grid-consumption source.
3. Select your home's cumulative grid-import energy sensor as the **consumption** entity.
4. For electricity cost, choose **Use an entity with current price**.
5. Select **Eversource Total Electricity Rate** (`sensor.eversource_total_electricity_rate`).
6. Save the Energy configuration.

If you already have grid consumption configured, do not add a second copy of the same consumption sensor just to use Eversource pricing. Edit the existing grid-consumption source and assign the Eversource total-rate entity as its current-price source.

### 3. Use the total rate, not the individual components

The price supplied to the Energy dashboard should be:

```text
Eversource supply rate
+ all variable Eversource delivery charges
= sensor.eversource_total_electricity_rate
```

Do **not** select only `sensor.eversource_supply_rate`, because that omits delivery charges. Likewise, do not select only `sensor.eversource_delivery_rate`, because that omits supply.

### Fixed monthly customer charge

`sensor.eversource_customer_charge` is intentionally excluded from the Energy dashboard price sensor. A fixed monthly charge is not a per-kWh cost; dividing it across usage would make the apparent electricity price change depending on how much energy you happened to consume that month.

As a result, the Energy dashboard's calculated electricity cost is best understood as your **variable energy cost**. It will not exactly reproduce the final Eversource bill because the fixed monthly customer charge is tracked separately, and future tariff structures may contain other non-variable bill items.

### When rates change

The integration checks Eversource periodically and updates the price sensor when the public tariff changes. Home Assistant then uses the current price for energy consumed after that update. The integration does not rewrite historical Energy dashboard costs or retroactively rebill older consumption periods.

This is especially important when an Eversource billing period crosses a tariff effective date: the utility bill may split usage across old and new tariff periods, while Home Assistant records costs based on the rate states it observed over time.

### Verifying the setup

After configuration:

1. Open **Developer tools → States**.
2. Find `sensor.eversource_total_electricity_rate`.
3. Confirm it has a numeric value and a unit of `USD/kWh`.
4. Return to **Settings → Dashboards → Energy** and verify the entity is selected as the current price for your grid-consumption source.
5. Allow Home Assistant time to collect additional consumption statistics before expecting cost data to appear in the Energy dashboard.

If the Eversource rate sensor is available but cost data is missing, first verify that your **consumption sensor** itself is valid for the Energy dashboard and is being recorded. This integration cannot calculate Energy dashboard costs without a working kWh consumption source.

## How the tariff is calculated

The integration retrieves Eversource's public supply rate and the individual variable delivery components for the selected tariff. The variable delivery components are normalized to USD/kWh and summed using exact decimal arithmetic.

Conceptually:

```text
supply rate
+ distribution
+ transmission
+ regulatory adjustments
+ system-benefit charges
+ other per-kWh riders/credits
= total variable electricity rate
```

Negative tariff adjustments are preserved as credits. The fixed monthly customer charge is parsed and exposed separately.

## Privacy, data source, and disclaimer

The integration accesses only Eversource's public tariff pages. It does not use browser automation, logged-in sessions, private APIs, or the Sitefinity personalization endpoint. If retrieval or parsing fails, Home Assistant retains prior coordinator data rather than publishing a fabricated rate.

This project is unofficial and is not affiliated with, endorsed by, or sponsored by Eversource.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `PYTHONPATH=. pytest`, `ruff check .`, `ruff format --check .`, and `pre-commit run --all-files`. Release Please owns versions and `CHANGELOG.md`; do not manually create release entries or tags.
