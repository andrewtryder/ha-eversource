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
| Connecticut — Rate 1 (Residential) | **Supported** from public tariff data |
| Western Massachusetts — R1 Non-Heating | **Supported** from public tariff data (Fixed / Monthly Variable Basic Service) |
| Eastern Massachusetts — R1 Non-Heating | **Supported** from public tariff data (Fixed / Monthly Variable Basic Service + service area) |

**Electricity only.** Natural gas is not supported. The current integration also assumes **Eversource default service supply**; third-party supplier pricing, time-of-use tariffs (including CT Rate 7), heat-pump rates, and assistance rates are not yet supported.

## What it does

- Checks public Eversource tariff pages daily by default; the interval can be changed from the integration's Configure menu.
- Requires no Eversource login, account number, API key, or private account data.
- Calculates the all-in **variable** electricity rate: supply + per-kWh delivery charges and credits.
- Keeps the fixed monthly customer charge separate so it is not incorrectly applied as a per-kWh price.

## Install and configure

Use the **Open in HACS** button above, install **Eversource Rates**, and restart Home Assistant if prompted. If needed, add this repository to HACS as a custom repository of type **Integration**.

Then go to **Settings → Devices & services → Add integration → Eversource Rates** and select your service territory and electric rate class.

### Finding your rate class

Look at the detailed **Delivery** section of your Eversource electric bill, typically on page 2. The rate designation is usually shown near the delivery-charge breakdown.

- New Hampshire residential: look for **Rate R** or **Rate R Residential Services**.
- Connecticut residential: look for **Rate 1**.
- Western Massachusetts residential: look for **R1** (Residential, Non-Heating), then choose Fixed or Monthly Variable Basic Service.
- Eastern Massachusetts residential: look for **R1** (Residential, Non-Heating), choose Fixed or Monthly Variable Basic Service, then select Greater Boston / Cambridge / South Shore or Cape Cod / Martha's Vineyard.
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

New Hampshire Rate R keeps short entity IDs. Connecticut Rate 1 uses territory-prefixed IDs such as `sensor.eversource_ct_1_total_electricity_rate`. Massachusetts R1 includes the supply plan (and for EMA, service area), such as `sensor.eversource_wma_r1_fixed_total_electricity_rate` or `sensor.eversource_ema_r1_fixed_cape_total_electricity_rate`.

| Entity (NH Rate R) | Purpose |
| --- | --- |
| `sensor.eversource_total_electricity_rate` | Supply + variable delivery in USD/kWh; use this in the Energy dashboard |
| `sensor.eversource_supply_rate` | Current Eversource default-service supply price |
| `sensor.eversource_delivery_rate` | Sum of variable Eversource delivery charges |
| `sensor.eversource_customer_charge` | Fixed monthly customer charge; not part of the per-kWh Energy price |

Individual delivery components are available as disabled-by-default diagnostic entities.

## Data updates and schedules

- **Tariff update interval**: Checks public Eversource tariff pages **every 24 hours** by default.
- **Configurable interval**: Open **Settings → Devices & services → Eversource Rates → Configure** to choose:
  - 6 hours
  - 12 hours
  - 24 hours (default)
  - 48 hours
  - 72 hours
  - 168 hours (7 days)
- **Immediate refresh on save**: Changing and saving the update interval automatically reloads the integration and triggers an immediate tariff refresh.
- **Repository schedules**: For clarity, this repository has three distinct schedules:
  1. *Tariff refresh*: 24-hour default in Home Assistant runtime (with 6h–168h user options).
  2. *GitHub Actions validation*: Runs daily in CI against local sanitized test fixtures (not a live scrape).
  3. *Dependabot*: Checks for dependency updates weekly on Mondays.

## Troubleshooting

### Enabling debug logging

To view detailed fetch and parse diagnostics, enable debug logging either via the UI:

1. Go to **Settings → Devices & services**.
2. Find the **Eversource Rates** card.
3. Click the menu (**⋮**) and select **Enable debug logging**.

Or add to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.eversource_rates: debug
```

### Forcing an immediate refresh

Enabling debug logging does not by itself trigger a tariff refresh. To see log output immediately:

1. Enable debug logging (via the steps above).
2. Click the menu (**⋮**) on the Eversource Rates card and select **Reload**.
3. Setup will run an immediate coordinator refresh.

When retrieval succeeds, you will see debug entries similar to:

```text
DEBUG (MainThread) [custom_components.eversource_rates.api] Refreshing tariff for nh/r
DEBUG (MainThread) [custom_components.eversource_rates.api] Retrieved tariff page from ...: status=200, bytes=...
DEBUG (MainThread) [custom_components.eversource_rates.api] Parsed Eversource nh r tariff with 6 delivery components: supply=0.10444, effective=2026-08-01
```

If you do not see either a `Parsed Eversource ...` message or an `UpdateFailed` warning after reloading, check that debug logging is enabled for the `custom_components.eversource_rates` namespace.

## Known limitations

- **Electricity only**: Natural gas tariffs are not supported.
- **Default service only**: Assumes Eversource standard default Basic Service supply. Third-party competitive energy suppliers, electric vehicle / time-of-day tariffs (including CT Rate 7), heat-pump discounts, and financial hardship/assistance rates are not supported.
- **Timezone**: All Eversource territories operate in Eastern Time (`America/New_York`). Tariff effective dates are evaluated using Eastern Time, regardless of the host system or container timezone.
- **Price-only integration**: Does not monitor real-time consumption; a separate cumulative grid energy sensor (kWh) is required for the Home Assistant Energy dashboard.
- **Historical data**: Home Assistant applies current rates to energy recorded going forward; past energy costs in the Energy dashboard are not retroactively recalculated.

## Uninstalling

To remove Eversource Rates:

1. Open **Settings → Dashboards → Energy** and remove `sensor.eversource_total_electricity_rate` from your electricity grid configuration.
2. Go to **Settings → Devices & services**.
3. On the **Eversource Rates** card, click the menu (**⋮**) and select **Delete**.
4. If installed via HACS, you can then remove it from the HACS integration list.

## Notes

Rates are parsed from public Eversource pages using exact decimal arithmetic. If a public page becomes unavailable or changes in an unsafe way, the integration fails closed rather than publishing a fabricated price. Developers can use `tools/fetch_eversource_rates.py` for a manual live fetch/parse check against the public New Hampshire tariff pages.

This project is unofficial and is not affiliated with, endorsed by, or sponsored by Eversource.

For development details, see [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/hacs-integration-design.md](docs/hacs-integration-design.md).
