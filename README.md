# Eversource Rates for Home Assistant

[![Validate](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![GitHub release](https://img.shields.io/github/v/release/andrewtryder/ha-eversource)](https://github.com/andrewtryder/ha-eversource/releases)
[![License](https://img.shields.io/github/license/andrewtryder/ha-eversource)](LICENSE)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewtryder&repository=ha-eversource&category=integration)

Unofficial Home Assistant custom integration for public **Eversource electricity** tariff rates.

## Current support

| Territory | Electric rate | Status |
| --- | --- | --- |
| New Hampshire | Residential Rate R | Supported and maintainer-tested |
| Connecticut | — | Investigated, not yet supported |
| Eastern Massachusetts | — | Investigated, not yet supported |
| Western Massachusetts | — | Investigated, not yet supported |

This integration currently supports **electricity tariffs only**. Natural-gas tariffs are not supported. Eversource gas tariffs use a separate billing and rate model and are outside the scope of this integration.

The setup selectors only list production-supported combinations. Investigated CT/MA territory identifiers are not offered until runtime tariff support exists.

The maintainer currently validates this integration against a real Eversource New Hampshire Residential Rate R account and bill. Other Eversource electric territories may later be added using public tariff documents and automated parser tests, but should not be described as maintainer-tested until verified against real-world billing.

## Features

- Retrieves public, server-rendered Eversource supply and delivery tariff pages about every 12 hours.
- Does not require an Eversource login, account number, API key, or stored credential.
- Uses the public audience-selection cookie `.SEGMENT=nh`; it is not an authenticated account cookie.
- Uses exact `Decimal` arithmetic for supply and delivery tariff components.
- Exposes an all-in variable electricity-rate sensor intended for Home Assistant's Energy dashboard.
- Keeps the fixed monthly customer charge separate from the per-kWh price.

## Installation

Add `https://github.com/andrewtryder/ha-eversource` to HACS as a custom repository of type **Integration**, install **Eversource Rates**, and restart Home Assistant.

For a manual installation, copy `custom_components/eversource_rates` to your Home Assistant configuration directory's `custom_components` folder and restart Home Assistant.

## Configuration

Go to **Settings → Devices & services → Add integration**, then select **Eversource Rates**.

1. Choose your **service territory**.
2. Choose your **electric rate class**.

Today that means **New Hampshire** and **Residential Rate R**. Setup validates public tariff retrieval before creating the entry.

## Finding your electric rate class

Open your most recent Eversource **electric** bill and look at the detailed Delivery section, typically on page 2. The rate designation is usually shown immediately above or near the delivery-charge breakdown.

Examples of what a bill rate designation may look like:

- New Hampshire: `Rate R`, `Rate R Residential Services`
- Massachusetts examples (not currently supported by this integration): `R1-Residential Non-Heating`, `R1HP-Residential Heat Pump`, `R3-Residential Heating`

Bill layouts vary somewhat between Eversource territories. If you cannot determine your rate:

1. Re-check the Delivery section of the bill.
2. Check Eversource's public Rates & Tariffs page for your location.
3. Contact Eversource if necessary.

Do not send account numbers or private bill details to this project.

### Electric rate class vs electricity supplier

Your **electric rate class** and your **electricity supplier** are different concepts.

- The electric rate class determines Eversource **delivery** pricing.
- Electricity **supply** may come from Eversource default/basic service, municipal or community aggregation, or a competitive third-party supplier.

Version 0.x of this integration uses Eversource **default service** supply pricing from the public tariff pages. It does not model third-party supplier contract prices. Do not confuse a supplier name on your bill with the Eversource delivery rate class.

## Entities

| Entity | Meaning | Intended use |
| --- | --- | --- |
| `sensor.eversource_supply_rate` | Eversource supply price in USD/kWh | Reference / diagnostics |
| `sensor.eversource_delivery_rate` | Sum of variable Eversource delivery charges in USD/kWh | Reference / diagnostics |
| `sensor.eversource_total_electricity_rate` | Supply + all variable delivery charges in USD/kWh | **Home Assistant Energy dashboard current price** |
| `sensor.eversource_customer_charge` | Fixed monthly customer charge | Reference only; do not use as a per-kWh price |

Individual delivery components are also available as diagnostic entities and are disabled by default. Newly published delivery riders are included in the total rate immediately after a successful refresh; a newly discovered rider's individual diagnostic entity appears after the integration is reloaded.

## Energy measurement requirement

This integration does **not** measure household electricity consumption.

It provides the current electricity tariff as a price in **USD/kWh**.

To calculate energy costs in Home Assistant, you need a separate entity that measures cumulative electricity consumption in **kWh** (energy). That entity may come from Sense, a smart meter, an energy monitor, another Home Assistant integration, or other metering hardware — if that source exposes a compatible cumulative kWh entity. Instantaneous power sensors in **kW** or **W** are not sufficient by themselves.

## Using Eversource Rates with the Home Assistant Energy dashboard

Home Assistant combines your consumption sensor with this integration's price sensor:

```text
Consumption sensor (kWh)
          +
Eversource Total Electricity Rate (USD/kWh)
          =
Home Assistant variable electricity cost
```

```text
Energy monitor / meter
        |
        | kWh
        v
Home Assistant Energy Dashboard
        ^
        | USD/kWh
        |
Eversource Rates
  sensor.eversource_total_electricity_rate
```

`sensor.eversource_total_electricity_rate` is the price entity. It includes Eversource supply plus all variable per-kWh delivery components. It excludes the fixed monthly customer charge, because applying a fixed charge as a changing per-kWh tariff would distort Home Assistant's incremental cost calculation.

This integration alone is not enough to create Energy Dashboard consumption data. You still need a working cumulative kWh grid-consumption source.

### Energy dashboard setup steps

1. Install and configure **Eversource Rates**.
2. Confirm `sensor.eversource_total_electricity_rate` has a valid numeric state and unit `USD/kWh` (**Developer tools → States**).
3. Open **Settings → Dashboards → Energy**.
4. Under **Electricity grid**, add or edit **Grid consumption** using your cumulative kWh consumption entity.
5. For cost, choose **Use an entity with current price**.
6. Select **Eversource Total Electricity Rate** (`sensor.eversource_total_electricity_rate`).
7. Save.
8. Allow Home Assistant statistics and cost data time to populate.

If you already have grid consumption configured, do not add a second copy of the same consumption sensor just to use Eversource pricing. Edit the existing grid-consumption source and assign the Eversource total-rate entity as its current-price source.

### Use the total rate, not the individual components

```text
Eversource supply rate
+ all variable Eversource delivery charges
= sensor.eversource_total_electricity_rate
```

Do **not** select only `sensor.eversource_supply_rate` (omits delivery) or only `sensor.eversource_delivery_rate` (omits supply).

### Fixed monthly customer charge

`sensor.eversource_customer_charge` is intentionally excluded from the Energy dashboard price sensor. The dashboard's calculated electricity cost is best understood as your **variable energy cost**. It will not exactly reproduce the final Eversource bill because the fixed monthly customer charge is tracked separately, and future tariff structures may contain other non-variable bill items.

### When rates change

The integration checks Eversource periodically and updates the price sensor when the public tariff changes. Home Assistant then uses the current price for energy consumed after that update. The integration does not rewrite historical Energy dashboard costs or retroactively rebill older consumption periods.

This is especially important when an Eversource billing period crosses a tariff effective date: the utility bill may split usage across old and new tariff periods, while Home Assistant records costs based on the rate states it observed over time.

### Troubleshooting missing Energy costs

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
