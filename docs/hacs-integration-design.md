# Eversource Rates — integration architecture

This document describes the Home Assistant / HACS integration architecture for public Eversource **electricity** tariffs as of v0.3.0+.

Production code under `custom_components/eversource_rates/` is authoritative. This document explains how the integration works and notes design decisions. It is **not** a promise of natural gas, time-of-day, or third-party supplier support.

---

## Current production scope

| Item | Value |
| --- | --- |
| Domain / path | `eversource_rates` / `custom_components/eversource_rates` |
| Commodity | Electricity only (natural gas is out of scope) |
| Supported territories | New Hampshire, Connecticut, Western Massachusetts, Eastern Massachusetts |
| Supported rate classes | NH: Residential Rate R<br>CT: Rate 1 (Residential)<br>WMA: R1 - Residential Non-Heating (Fixed & Monthly Variable Basic Service)<br>EMA: R1 - Residential Non-Heating (Fixed & Monthly Variable Basic Service; Main & Cape service areas) |
| Supply model | Eversource default / basic service from public tariff pages |
| Timezone | All service territories evaluate tariff calendar dates in Eastern Time (`America/New_York`) |
| Tariff refresh schedule | Every **24 hours** by default; configurable via Options (6 / 12 / 24 / 48 / 72 / 168 hours) |
| Authentication | None — unauthenticated public HTTPS endpoints; Sitefinity audience cookie `.SEGMENT=nh` for NH |

### Repository schedules

To avoid confusion between polling and repo maintenance, three distinct schedules exist:

1. **Home Assistant Tariff Refresh**: Defaults to every **24 hours** via `DataUpdateCoordinator`. Configurable in integration Options to 6, 12, 24, 48, 72, or 168 hours (7 days). Saving new options immediately reloads the entry and performs a refresh.
2. **GitHub Validation Workflow**: Runs **daily** at `00:00 UTC` via GitHub Actions (`validate.yml`). Executes HACS validation, `hassfest`, Ruff linting/formatting, and `pytest` against local test fixtures. It does **not** scrape live Eversource pages.
3. **Dependabot Checks**: Runs **weekly** on Mondays for GitHub Actions, Python packages, and pre-commit hooks.

---

## Module layout

```text
custom_components/eversource_rates/
├── __init__.py          # Config-entry setup; coordinator lifecycle, sensor platform forward
├── manifest.json        # Domain, HACS metadata, requirements (version via Release Please)
├── const.py             # DOMAIN, URLs, intervals, EVERSOURCE_TIME_ZONE, TERRITORIES
├── tariffs.py           # Tariff definitions, selections, and entry-data resolution
├── sources.py           # Public endpoint definitions (TariffSource) per territory/rate
├── config_flow.py       # Multi-step config flow + OptionsFlowWithReload
├── coordinator.py       # DataUpdateCoordinator wrapper (EversourceRatesCoordinator)
├── api.py               # EversourceClient (async concurrent fetch & validation)
├── models.py            # Immutable slotted dataclasses (SupplyRate, DeliveryRates, EversourceRates)
├── parsers/             # Territory-specific tariff parsers (fail-closed)
│   ├── __init__.py      # Parser dispatch (parse_tariff, get_tariff_parser)
│   ├── common.py        # Shared parsing helpers (decimal, component_key, is_summary_row)
│   ├── nh.py            # New Hampshire Rate R parser
│   ├── ct.py            # Connecticut Rate 1 parser
│   └── ma.py            # Massachusetts R1 parser (WMA & EMA)
├── sensor.py            # Primary rate sensors + diagnostic delivery-component sensors
├── entity_ids.py        # Stable object-ID generation (preserves legacy NH Rate R IDs)
├── strings.json         # Integration string definitions for hassfest
└── translations/
    └── en.json          # Authoritative English UI translations
```

Developer utility (not part of the HA runtime path):

```text
tools/fetch_eversource_rates.py
```

---

## Data flow

```text
Public supply URL  ──┐
                     ├── EversourceClient (aiohttp ClientSession)
Public delivery URL ─┘              │
                                    ▼
                         parsers.parse_tariff()
                                    │
                                    ▼
                             EversourceRates
                                    │
                                    ▼
                       EversourceRatesCoordinator
                                    │
                                    ▼
                      Primary + diagnostic sensors
```

1. **Fetch** — Asynchronous concurrent `GET` of the public supply and delivery tariff pages. NH uses generic URLs with `.SEGMENT=nh` cookie; CT, WMA, and EMA use territory-suffixed URLs (`/ct`, `/wma`, `/ema`).
2. **Timezone Evaluation** — Effective date intervals are evaluated in Eastern Time (`America/New_York`), ensuring consistent period selection regardless of the Home Assistant host system timezone (such as UTC).
3. **Parse** — Territory parsers extract supply and delivery tables into exact `Decimal` values. Missing required riders, malformed units, conflicting duplicates, or mismatching delivery totals fail closed.
4. **Coordinate** — `DataUpdateCoordinator` handles scheduling and retains prior rate data when a refresh encounters an error (`UpdateFailed`). Successful refreshes publish an updated `retrieved_at` timestamp.
5. **Expose** — Sensors publish current rates for the Energy dashboard and diagnostics.

---

## Config and options flow

The configuration flow dynamically asks for required attributes based on territory:

1. **Service territory**: NH, CT, WMA, or EMA.
2. **Electric rate class**: Appropriate rate class for the territory (e.g. Rate R, Rate 1, or R1).
3. **Supply plan** *(MA only)*: Fixed Basic Service or Monthly Variable Basic Service.
4. **Service area** *(EMA only)*: Greater Boston / Cambridge / South Shore or Cape Cod / Martha's Vineyard (reflecting differing Energy Efficiency riders).

Before creating the config entry, the flow tests live connectivity and parsing against Eversource to fail fast if pages are unreachable or changed.

### Options flow

Uses Home Assistant's `OptionsFlowWithReload` pattern. Users can select an update interval: 6, 12, 24, 48, 72, or 168 hours (7 days). Submitting options automatically reloads the entry, immediately executing a fresh coordinator refresh with the new interval.

---

## Entity model

Rate sensors use `SensorStateClass.MEASUREMENT` and omit `SensorDeviceClass.MONETARY` (which is inappropriate for USD/kWh).

### Primary entities

- **Total Electricity Rate** (`sensor.eversource_total_electricity_rate` for NH; territory-prefixed for others): Supply + variable delivery in USD/kWh. This is the entity to configure in the Energy dashboard.
- **Supply Rate**: Current Eversource default-service supply price.
- **Delivery Rate**: Sum of all variable Eversource delivery charges.
- **Customer Charge**: Fixed monthly customer charge (USD/month); intentionally excluded from the per-kWh Energy price.

### Diagnostic delivery components

Disabled-by-default diagnostic sensors expose each parsed USD/kWh delivery rider (e.g. Transmission Charge, Distribution Charge, Stranded Cost Recovery). If a rider disappears from the tariff, the entity toggles to unavailable; if it reappears, it becomes available again.

---

## Energy dashboard arithmetic

All financial math uses exact `decimal.Decimal`:

```text
supply
+ Σ variable delivery components
= total_variable_rate  →  Total Electricity Rate sensor
```

The fixed monthly customer charge is **excluded** from the Energy dashboard price so incremental kWh costs are not distorted.

---

## Release and supply-chain hygiene

- **Release Please** manages `manifest.json` version, `CHANGELOG.md`, and GitHub releases. Never manually bump release versions.
- **Quality gates**: CI enforces 100% passes on HACS validation, `hassfest`, Ruff linting/formatting, and a strict $\ge 96\%$ test coverage threshold.
