# Eversource Rates for Home Assistant

<img src="custom_components/eversource_rates/brand/icon.png" alt="Eversource Rates integration icon" width="100">

See public Eversource electricity rates in Home Assistant and use the current price to estimate your variable electricity costs.

[![Latest release](https://img.shields.io/github/v/release/andrewtryder/ha-eversource?style=flat-square)](https://github.com/andrewtryder/ha-eversource/releases/latest)
[![Validation on main](https://img.shields.io/github/actions/workflow/status/andrewtryder/ha-eversource/validate.yml?branch=main&style=flat-square&label=validation)](https://github.com/andrewtryder/ha-eversource/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/andrewtryder/ha-eversource?style=flat-square)](LICENSE)
[![HACS custom integration](https://img.shields.io/badge/HACS-Custom-orange?style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewtryder&repository=ha-eversource&category=integration)

## What can I do with it?

- Show the current supply, delivery, and combined variable electricity rates.
- Use the combined rate with a separate energy sensor in the Home Assistant Energy dashboard.
- Optionally monitor public, municipality-level outage reports. This does not indicate whether your own home has power.

No Eversource login, account number, or API key is required.

## Requirements and compatibility

You need Home Assistant with HACS (or the built-in Home Assistant Marketplace in **2026.11+**) and a supported Eversource electricity territory and rate:

| Territory | Supported residential rate |
| --- | --- |
| New Hampshire | Rate R (maintainer-tested) |
| Connecticut | Rate 1 |
| Western Massachusetts | R1 Non-Heating, Fixed or Monthly Variable Basic Service |
| Eastern Massachusetts | R1 Non-Heating, Fixed or Monthly Variable Basic Service, with service area |

The integration assumes Eversource default-service supply. Natural gas, third-party supplier prices, time-of-use rates including Connecticut Rate 7, heat-pump rates, and assistance rates are not supported.

## Install with HACS or Home Assistant Marketplace

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewtryder&repository=ha-eversource&category=integration)

1. Click the **Open your Home Assistant instance** button above (backwards compatible: opens **HACS** on earlier versions and the built-in **Home Assistant Marketplace** on **2026.11+**), or manually add `https://github.com/andrewtryder/ha-eversource` as a custom repository in the **Integration** category.
2. Install **Eversource Rates** and restart Home Assistant if prompted.

## First-time setup

1. Go to **Settings → Devices & services → Add integration** and select **Eversource Rates**.
2. Choose your territory and electric rate class. Massachusetts customers also choose a supply plan; Eastern Massachusetts customers select their service area.
3. If unsure of your rate, look in the detailed **Delivery** section of your electric bill: NH residential is Rate R, Connecticut residential is Rate 1, and the supported Massachusetts residential rate is R1 Non-Heating. Your rate class is different from your electricity supplier.

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

## What you'll see in Home Assistant

The total electricity rate combines supply and variable delivery charges in USD/kWh. Supply, delivery, and fixed monthly customer charge sensors are also available; individual delivery components are disabled by default. Entity IDs vary by territory and plan.

Enable optional [municipality outage monitoring](docs/outages.md) through **Settings → Devices & services → Eversource Rates → Configure**. It reports aggregate customers without power in a selected municipality, not the status of a particular address.

Rates refresh every 24 hours by default. In **Configure**, choose an interval from 6 hours to 7 days; saving an interval reloads the integration and refreshes it immediately.

## Common problems and troubleshooting

- Confirm that the territory, rate class, and Massachusetts supply plan match your bill.
- If a rate is unavailable, check Home Assistant logs and try reloading the integration. The [troubleshooting guide](docs/troubleshooting.md) explains debug logging and refreshes.
- Outage data applies to a municipality, not an individual meter; see [outage monitoring](docs/outages.md).

## Limitations, safety, and privacy

This integration supplies **price data only**. A separate cumulative grid-consumption sensor in kWh is required for the Energy dashboard. The estimate excludes the fixed monthly customer charge and is not a complete electricity bill. Home Assistant does not retroactively recalculate historical energy costs when rates change. Effective dates use Eastern Time.

If a public source becomes unavailable or changes in a way the integration cannot interpret safely, it fails closed rather than publishing a fabricated price.

## More documentation

- [Troubleshooting](docs/troubleshooting.md) and [outage monitoring](docs/outages.md)
- [Contributing and development](CONTRIBUTING.md)
- [Integration design](docs/hacs-integration-design.md)

## Support and license

Report issues on [GitHub](https://github.com/andrewtryder/ha-eversource/issues). To uninstall, first remove the price sensor from the Energy dashboard, then delete the integration under **Settings → Devices & services** and remove it from HACS if desired.

This unofficial community project is not affiliated with, endorsed by, or sponsored by Eversource. See the [license](LICENSE).
