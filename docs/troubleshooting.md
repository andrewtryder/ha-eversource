# Troubleshooting Eversource Rates


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
