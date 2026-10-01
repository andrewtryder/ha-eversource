# Municipality Outage Monitoring

Eversource Rates includes optional **municipality-level aggregate outage monitoring** powered by Eversource's public outage map data.

> [!IMPORTANT]
> **Municipality aggregate only:**
> This feature answers: *“Does Eversource currently report any customers without power in my selected municipality?”*
> It does **NOT** monitor your specific meter or service address and does **NOT** prove your home specifically is without power.

---

## How it works

- **Public data source**: Data is retrieved from Eversource's public outage interval JSON feed (`outagemap.eversource.com`).
- **No authentication required**: No Eversource login, account numbers, meter IDs, or private data are required or collected.
- **Isolated polling**: Outage monitoring runs on its own independent update interval (5 minutes) and dedicated coordinator. Any temporary outage API failure will **never** interrupt or degrade tariff price sensors.

---

## Configuration

Outage monitoring is **optional** and disabled by default.

To enable or modify outage monitoring:

1. In Home Assistant, navigate to **Settings → Devices & services**.
2. Select your **Eversource Rates** integration entry and click **Configure**.
3. In the options dialog, check **Enable municipality outage monitoring** and click **Submit**.
4. In the next step, select your municipality from the list of towns/cities reported in your territory's public outage report.
5. Click **Submit**. The integration reloads and starts monitoring outages for your municipality.

To disable outage monitoring, open **Configure**, uncheck **Enable municipality outage monitoring**, and click **Submit**.

---

## Entities

When enabled, a separate logical device is created for outage monitoring (e.g., `Eversource Outage (Concord)`):

| Entity | Type | Description |
| --- | --- | --- |
| `binary_sensor.<id>_outage` | Binary Sensor (`problem`) | `on` if Eversource reports 1 or more customers without power in the municipality (`off` if 0). |
| `sensor.<id>_customers_out` | Sensor | Current count of customers reported without power. |
| `sensor.<id>_percent_out` | Sensor (`%`) | Percentage of customers reported without power. |
| `sensor.<id>_customers_served` | Sensor (Diagnostic) | Total customers served in the municipality (disabled by default). |

### Attributes

The outage binary sensor and sensors include helpful diagnostic attributes:
- `municipality`: Name of the selected municipality (e.g. `CONCORD`).
- `territory`: Service territory code (`nh`, `ct`, `ema`, `wma`).
- `customers_out`: Current count of customers without power.
- `customers_served`: Total customers served.
- `percent_out`: Percentage of customers without power.
- `retrieved_at`: ISO 8601 timestamp of data retrieval.
- `source_url`: URL of the public territory report.

---

## Scope & Limitations

- **Aggregate only**: Provides town/city-level totals as published on the public map.
- **No individual incident tracking**: Incident causes, crew statuses, polygons, and Estimated Times of Restoration (ETRs) are not provided in municipality-level summary reports and are not supported.
