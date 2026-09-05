# Supply Rate Source Analysis

## 1. Supply Rate Document Overview
- **URL:** `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates`
- **Method:** `GET`
- **Response Status:** `200 OK`
- **MIME Type:** `text/html; charset=utf-8`
- **Target Value:** `0.14009` USD/kWh (New Hampshire Residential Rate R)

---

## 2. Server-Rendered HTML Architecture
The rate does not originate from JavaScript bundles, hydration state, or a dynamic REST/GraphQL API. It is rendered directly into the HTML document stream by Progress Sitefinity CMS.

The content block is segmented for the New Hampshire audience when the request carries the cookie:
```http
Cookie: .SEGMENT=nh
```

### Observed Semantic Element Structure
The rate appears in a standard Sitefinity content block (`div.sfContentBlock.sf-Long-text`) inside a `div.cms` container:

```html
<div class="cms">
    <div class="sfContentBlock sf-Long-text">
        <h2>Current Supply Rates</h2>
        <p>The supply rate for Rate R will be $0.14009 per kWh August 1, 2026 through January 31, 2027.</p>
        <p>If you have a different rate, visit our&nbsp;<a href="/docs/default-source/rates-tariffs/nh-summary-rates.pdf?sfvrsn=eefadaef_44" target="_blank">full list of New Hampshire electric rates</a>.</p>
    </div>
</div>
```

---

## 3. Fingerprint Analysis

| Fingerprint | Found in Initial HTML? | Offset / Location | Context / Semantic Role |
|---|---|---|---|
| `0.14009` | **Yes** | Offset ~50,779 | Rate value in paragraph under `<h2>Current Supply Rates</h2>` |
| `Current Supply Rates` | **Yes** | Offset ~50,715 | Section heading (`<h2>`) |
| `Rate R` | **Yes** | Offset ~50,763 | Tariff class identifier |
| `January 31, 2027` | **Yes** | Offset ~50,818 | Expiration date of current tariff cycle |
| `August 1, 2026` | **Yes** | Offset ~50,793 | Effective start date of current tariff cycle |

---

## 4. Tariff Cycle & Schedule
The page explicitly defines the tariff frequency and schedule:
> *"Supply rates change twice each year—on February 1 and August 1—as demand for energy increases or decreases."*

This informs the Home Assistant integration polling schedule: because rates only adjust semi-annually, high-frequency polling is unnecessary.

---

## 5. Recommended Extraction Strategy
To avoid fragile CSS positional selectors (e.g. `div:nth-child(4) > p:nth-child(2)`), extraction should use semantic pattern matching:

1. Search elements within the main content container (`div.cms`, `div.sfContentBlock`, or `body`) for the pattern:
   ```regex
   Rate\s+R\s+will\s+be\s+\$([0-9.]+)\s+per\s+kWh(?:\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}))?
   ```
2. Extract the rate as a `Decimal`:
   - Match group 1: `0.14009` (USD/kWh)
   - Match group 2 (optional start date): `"August 1, 2026"`
   - Match group 3 (optional end date): `"January 31, 2027"`
3. Fallback:
   ```regex
   Rate\s+R.*?\$([0-9.]+)\s*(?:/|per)\s*kWh
   ```
4. Validate that the extracted rate falls within reasonable bounds (e.g. $0.02 – $0.80 / kWh).
