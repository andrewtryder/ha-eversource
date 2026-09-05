# Eversource Rates — integration architecture

This document describes the **current** Home Assistant / HACS integration architecture for public Eversource **electricity** tariffs.

Production code under `custom_components/eversource_rates/` is authoritative. This document is non-normative: it explains how the integration works today and notes future direction. It is **not** a promise of Connecticut, Massachusetts, gas, time-of-day, or third-party supplier support.

For CT / Eastern MA / Western MA research notes, see [investigation/multi_territory_architecture.md](../investigation/multi_territory_architecture.md).

---

## Current production scope

| Item | Value |
| --- | --- |
| Domain / path | `eversource_rates` / `custom_components/eversource_rates` |
| Commodity | Electricity only (natural gas is out of scope) |
| Territory | New Hampshire |
| Rate class | Residential Rate R |
| Supply model | Eversource default / basic service from public tariff pages |
| Polling | Every **12 hours** via `DataUpdateCoordinator` (not user-configurable) |
| Auth | None — public HTTP only; Sitefinity audience cookie `.SEGMENT=nh` |

Setup selectors only offer production-supported combinations. Investigated CT/MA identifiers must not appear in the UI until runtime parsers exist.

---

## Module layout

```text
custom_components/eversource_rates/
├── __init__.py          # Config-entry setup; builds client + coordinator
├── manifest.json        # Domain, HACS metadata, requirements (version via Release Please)
├── const.py             # DOMAIN, URLs, UPDATE_INTERVAL, TERRITORIES
├── config_flow.py       # Two-step flow: territory → electric rate class
├── coordinator.py       # DataUpdateCoordinator wrapper
├── api.py               # EversourceClient (async public fetch)
├── parser.py            # Semantic HTML → Decimal models (fail-closed)
├── models.py            # Immutable SupplyRate / DeliveryRates / EversourceRates
├── sensor.py            # Primary + diagnostic delivery-component sensors
├── entity_ids.py        # Stable object-ID strategy (legacy NH Rate R short IDs)
├── strings.json
└── translations/en.json
```

Developer utility (not part of the HA runtime path):

```text
tools/fetch_eversource_rates.py
```

---

## Data flow

```text
Public supply URL  ──┐
                     ├── EversourceClient (Cookie: .SEGMENT=<segment>)
Public delivery URL ─┘              │
                                    ▼
                              parser.py
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

1. **Fetch** — unauthenticated `GET` of the public supply and delivery tariff pages with the territory’s Sitefinity `.SEGMENT` cookie (NH uses `nh`).
2. **Parse** — BeautifulSoup + regex extract supply and delivery rows into `Decimal` values. Missing required NH riders, malformed units, conflicting duplicates, or conflicting delivery **total/subtotal** rows fail closed.
3. **Coordinate** — Home Assistant’s coordinator retains prior data when a refresh raises `UpdateFailed` (standard HA behavior). Successful refreshes always publish a new snapshot, including an updated `retrieved_at`.
4. **Expose** — sensors publish current prices for the Energy dashboard and diagnostics.

---

## Config flow

Two steps (labels in `strings.json` / `translations/en.json`):

1. **Service territory** — options from `TERRITORIES`.
2. **Electric rate class** — options from `Territory.supported_rate_classes` for the chosen territory.

Config entry data keys remain `territory` and `rate_class`. There is no polling-interval option.

---

## Entity model

Rate sensors use `SensorStateClass.MEASUREMENT` and **do not** use `SensorDeviceClass.MONETARY` (inappropriate for USD/kWh).

### Primary entities (NH Rate R object IDs)

| Entity ID | Meaning |
| --- | --- |
| `sensor.eversource_supply_rate` | Default-service supply USD/kWh |
| `sensor.eversource_delivery_rate` | Sum of variable delivery components USD/kWh |
| `sensor.eversource_total_electricity_rate` | Supply + variable delivery (Energy dashboard current price) |
| `sensor.eversource_customer_charge` | Fixed monthly customer charge (not a per-kWh price) |

Non-NH combinations would use `eversource_<territory>_<rate>_<key>` via `entity_ids.sensor_object_id()` once supported.

### Diagnostic delivery components

Disabled-by-default diagnostic sensors expose each parsed `/kWh` delivery rider. Entities are created for components present at setup. If a dynamic rider later disappears from the tariff, the entity stays registered and becomes **unavailable**; if it reappears, it becomes available again. Entity IDs are not deleted or recreated dynamically.

---

## Arithmetic and Energy dashboard

All money math uses exact `decimal.Decimal`.

```text
supply
+ Σ variable delivery components
= total_variable_rate  →  sensor.eversource_total_electricity_rate
```

The fixed monthly customer charge is **excluded** from the Energy dashboard price so Home Assistant’s incremental kWh cost is not distorted.

This integration provides **price only**. A separate cumulative **kWh** consumption sensor is required for Energy dashboard costs.

---

## Future territory architecture

Internal models already carry logical `territory` separately from Sitefinity `segment`. Production `TERRITORIES` currently lists New Hampshire Rate R, Connecticut Rate 1, and Massachusetts R1 (WMA/EMA).

---

## Versioning and CI

Release Please owns `manifest.json` version, `CHANGELOG.md`, and GitHub tags/releases. Do not manually bump versions.

See `.github/workflows/` for validation and release automation. Additional operator notes live in `docs/ci-cd.md` when that document is present on the branch.
