# Eversource Rates for Home Assistant

[![Validate](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/andrewtryder/ha-eversource)](https://github.com/andrewtryder/ha-eversource/releases)
[![License](https://img.shields.io/github/license/andrewtryder/ha-eversource)](LICENSE)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewtryder&repository=ha-eversource&category=integration)

Eversource Rates is an unofficial Home Assistant integration that retrieves public **Eversource electricity** tariffs and exposes a current **USD/kWh** price for the Home Assistant Energy dashboard.

It provides **price data only**. You still need a separate cumulative **kWh** consumption sensor from Sense, a smart meter, an energy monitor, or another Home Assistant integration.

## Support

| Territory / rate | Status |
| --- | --- |
| New Hampshire — Residential Rate R | **Supported and maintainer-tested** |
| Connecticut | Investigated, not yet supported |
| Eastern Massachusetts | Investigated, not yet supported |
| Western Massachusetts | Investigated, not yet supported |

**Electricity only.** Natural gas is not supported. The current integration also assumes **Eversource default service supply**; third-party supplier pricing and time-of-use tariffs are not yet supported.

## What it does

- Retrieves Eversource supply and delivery rates from public tariff pages about every 12 hours.
- Requires no Eversource login, account number, API key, or private account data.
- Calculates the all-in **variable** electricity rate: supply + per-kWh delivery charges and credits.
- Keeps the fixed monthly customer charge separate so it is not incorrectly applied as a per-kWh price.

## Install and configure

Use the **Open in HACS** button above, install **Eversource Rates**, and restart Home Assistant if prompted. If needed, add this repository to HACS as a custom repository of type **Integration**.

Then go to **Settings → Devices & services → Add integration → Eversource Rates** and select your service territory and electric rate class.

### Finding your rate class

Look at the detailed **Delivery** section of your Eversource electric bill, typically on page 2. The rate designation is usually shown near the delivery-charge breakdown. For the currently supported New Hampshire residential tariff, look for **Rate R** or **Rate R Residential Services**.

Your **rate class** is different from your electricity **supplier**. This integration currently uses Eversource default-service supply pricing.

## Home Assistant Energy dashboard

You need two things:

1. A cumulative grid-consumption sensor in **kWh**.
2. This integration's current-price sensor: `sensor.eversource_total_electricity_rate`.

To configure it:

1. Open **Settings → Dashboards → Energy**.
2. Add or edit **Grid consumption** using your cumulative kWh sensor.
3. For cost, choose **Use an entity with current price**.
4. Select **Eversource Total Electricity Rate** (`sensor.eversource_total_electricity_rate`).

Do not use only the supply or delivery sensor; the total-rate sensor combines both. The fixed monthly customer charge is intentionally excluded, so Home Assistant's calculated cost represents **variable electricity cost**, not an exact reproduction of the final utility bill.

## Main entities

| Entity | Purpose |
| --- | --- |
| `sensor.eversource_total_electricity_rate` | Supply + variable delivery in USD/kWh; use this in the Energy dashboard |
| `sensor.eversource_supply_rate` | Current Eversource default-service supply price |
| `sensor.eversource_delivery_rate` | Sum of variable Eversource delivery charges |
| `sensor.eversource_customer_charge` | Fixed monthly customer charge; not part of the per-kWh Energy price |

Individual delivery components are available as disabled-by-default diagnostic entities.

## Notes

Rates are parsed from public Eversource pages using exact decimal arithmetic. If a public page becomes unavailable or changes in an unsafe way, the integration fails closed rather than publishing a fabricated price. Developers can use `tools/fetch_eversource_rates.py` for a manual live fetch/parse check against the public New Hampshire tariff pages.

Home Assistant applies the current price to energy recorded after rate updates; this integration does not retroactively recalculate historical Energy dashboard costs.

This project is unofficial and is not affiliated with, endorsed by, or sponsored by Eversource.

For development details, see [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/hacs-integration-design.md](docs/hacs-integration-design.md).
