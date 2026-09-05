# Home Assistant / HACS Custom Integration Architecture

## 1. Executive Design Overview
This document outlines the architecture for the **Eversource New Hampshire Electricity Rates** custom integration for Home Assistant (distributable via HACS).

The integration delivers real-time and scheduled electricity tariff rates to Home Assistant, allowing users to:
- Accurately configure Home Assistant's built-in **Energy Dashboard**.
- Automate high-draw appliances (EV charging, heat pumps, battery storage, water heaters) based on dynamic or fixed tariff schedules.
- Track total electricity expenditure including fixed customer charges and individual delivery adjustments.

---

## 2. Core Architectural Principles
1. **Zero Credential Requirement:** Operates entirely over public, unauthenticated HTTP endpoints. Users never input passwords, account numbers, or session cookies.
2. **Deterministic Location Handling:** Uses the public `.SEGMENT=nh` cookie to guarantee New Hampshire Rate R data regardless of the host's network IP location.
3. **Robust Decimal Arithmetic:** Implements Python's `decimal.Decimal` throughout to prevent floating-point calculation errors on financial tariffs.
4. **Resilience & State Preservation:** Employs Home Assistant's `DataUpdateCoordinator` with stale-data preservation so that transient network glitches or temporary web hiccups never clear valid rate state.
5. **Low Polling Frequency:** Polls every 6 to 12 hours (with manual refresh support), reflecting the real-world tariff change schedule (bi-annual and quarterly).

---

## 3. Recommended Entity Model

### Primary Sensor Entities

| Entity ID | Friendly Name | State / Unit | State Class | Device Class | Description |
|---|---|---|---|---|---|
| `sensor.eversource_total_variable_rate` | Eversource Total Variable Rate | `0.25918` USD/kWh | `measurement` | `monetary` | Sum of Supply + Variable Delivery (used directly by Energy Dashboard) |
| `sensor.eversource_supply_rate` | Eversource Supply Rate | `0.14009` USD/kWh | `measurement` | `monetary` | Published standard default service supply rate |
| `sensor.eversource_delivery_rate` | Eversource Delivery Rate | `0.11909` USD/kWh | `measurement` | `monetary` | Sum of all variable delivery components |
| `sensor.eversource_customer_charge` | Eversource Monthly Customer Charge | `19.81` USD | `measurement` | `monetary` | Fixed monthly account fee |

### Diagnostic Entities (Delivery Breakdown)
Exposed as diagnostic sensors (disabled by default or under the Diagnostic category):

- `sensor.eversource_distribution_charge` (`0.06727` USD/kWh)
- `sensor.eversource_regulatory_reconciliation_adjustment` (`0.00296` USD/kWh)
- `sensor.eversource_pole_plant_adjustment` (`-0.00029` USD/kWh)
- `sensor.eversource_transmission_charge` (`0.04445` USD/kWh)
- `sensor.eversource_stranded_cost_recovery_charge` (`-0.00148` USD/kWh)
- `sensor.eversource_system_benefits_charge` (`0.00618` USD/kWh)

### Entity Attributes & Metadata
Primary sensors will expose metadata in `extra_state_attributes`:
```json
{
  "effective_start": "August 1, 2026",
  "effective_end": "January 31, 2027",
  "tariff_class": "Rate R (Residential)",
  "state": "NH",
  "source_urls": {
    "supply": "https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates",
    "delivery": "https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates"
  },
  "last_updated": "2026-09-05T17:15:00+00:00"
}
```

---

## 4. Integration Component Structure

```
custom_components/eversource_tariffs/
├── __init__.py           # Component setup and Coordinator initialization
├── manifest.json         # Integration manifest, domain, requirements, version
├── const.py              # Constants (DOMAIN, URLs, default intervals, ranges)
├── config_flow.py        # User UI setup flow in HA Settings -> Integrations
├── coordinator.py        # DataUpdateCoordinator managing fetches & caching
├── parser.py             # Parser logic (adapted from tools/fetch_eversource_rates.py)
├── sensor.py             # Sensor entity implementations
├── strings.json          # Internationalization / UI labels
└── translations/
    └── en.json
```

---

## 5. Implementation Details

### DataUpdateCoordinator Pattern
The `DataUpdateCoordinator` handles scheduling, error catching, and data distribution:

```python
class EversourceDataUpdateCoordinator(DataUpdateCoordinator[TariffRates]):
    """Manages fetching Eversource tariff rates."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Eversource NH Tariffs",
            update_interval=timedelta(hours=6),
        )
        self.session = session
        self._last_valid_data: Optional[TariffRates] = None

    async def _async_update_data(self) -> TariffRates:
        """Fetch data from Eversource."""
        try:
            data = await fetch_eversource_rates(session=self.session)
            self._last_valid_data = data
            return data
        except TariffParseError as err:
            _LOGGER.warning("Parsing Eversource tariffs failed: %s", err)
            if self._last_valid_data is not None:
                _LOGGER.info(
                    "Preserving last known valid tariffs from %s",
                    self._last_valid_data.retrieval_timestamp,
                )
                return self._last_valid_data
            raise UpdateFailed(f"Error fetching Eversource tariffs: {err}") from err
        except aiohttp.ClientError as err:
            if self._last_valid_data is not None:
                _LOGGER.info(
                    "Preserving last known valid tariffs during network outage"
                )
                return self._last_valid_data
            raise UpdateFailed(
                f"Network error communicating with Eversource: {err}"
            ) from err
```

### Config Flow Experience
Because no credentials are required, the config flow is remarkably simple:
1. User clicks **Add Integration** $\rightarrow$ **Eversource Rates**.
2. A single step confirms region (defaults to **New Hampshire — Rate R (Residential)**).
3. Option to select polling frequency (default: 6 hours).
4. Entry is created instantly; entities become available immediately.

---

## 6. Integration with Home Assistant Energy Dashboard
Home Assistant's Energy dashboard natively supports variable pricing entities:
1. Navigate to **Settings** $\rightarrow$ **Dashboards** $\rightarrow$ **Energy**.
2. Under **Electricity Grid** $\rightarrow$ **Grid Consumption**, edit the consumption meter.
3. Select **"Use an entity tracking the total costs"** or **"Use an entity with current price"**.
4. Choose `sensor.eversource_total_variable_rate`.
5. Home Assistant will automatically multiply hourly kWh consumption by the exact live tariff ($0.25918 / kWh), tracking accurate energy expenses over time.
