# Delivery Rate Source Analysis

## 1. Delivery Rate Document Overview
- **URL:** `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates`
- **Method:** `GET`
- **Response Status:** `200 OK`
- **MIME Type:** `text/html; charset=utf-8`
- **Target Table:** Rate R Delivery Components & Customer Charge

---

## 2. Server-Rendered HTML Architecture
Like the supply page, the delivery page does not require client-side execution, REST calls, or authentication. Delivery tariffs are server-side rendered directly into the HTML document inside a Sitefinity content block (`div.sfContentBlock`).

When requested with `Cookie: .SEGMENT=nh`, Sitefinity renders the New Hampshire residential Rate R delivery table:

```html
<div class="sfContentBlock sf-Long-text">
    <h2>Current Rate R Delivery Rates</h2>
    <p>Rate R pricing is the most common rate for residential customers. If you have a different rate, view our <a href="/docs/default-source/rates-tariffs/nh-summary-rates.pdf?sfvrsn=eefadaef_44" target="_blank">full list of New Hampshire electric rates</a> or see the <a href="/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-tariffs-rules" target="_blank">List and Applicability of Rates and Riders</a>.</p>
    <p>Delivery rates typically change four times a year – on January 1, February 1, August 1 and October 1.</p>
    <table class="table table-striped k-table">
        <thead>
            <tr>
                <th data-role="resizable" style="text-align: center" scope="col">Delivery Component</th>
                <th style="text-align: center" scope="col">Current Rate</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="text-align: left">Customer Charge (per month)</td>
                <td style="text-align: center">$19.81<br>(per month)</td>
            </tr>
            <tr>
                <td style="text-align: left">Distribution Charge (per kWh)</td>
                <td style="text-align: center">6.727<br>(¢/kWh)</td>
            </tr>
            <tr>
                <td style="text-align: left">Regulatory Reconciliation Adjustment (per kWh)</td>
                <td style="text-align: center">0.296<br>(¢/kWh)</td>
            </tr>
            <tr>
                <td style="text-align: left">Pole Plant Adjustment Mechanism (per kWh)</td>
                <td style="text-align: center">-0.029<br>(¢/kWh)</td>
            </tr>
            <tr>
                <td style="text-align: left">Transmission Charge</td>
                <td style="text-align: center">4.445<br>(¢/kWh)</td>
            </tr>
            <tr>
                <td style="text-align: left">Stranded Cost Recovery Charge (per kWh)</td>
                <td style="text-align: center">-0.148<br>(¢/kWh)</td>
            </tr>
            <tr>
                <td style="text-align: left">System Benefits Charge (per kWh)</td>
                <td style="text-align: center">0.618<br>(¢/kWh)</td>
            </tr>
        </tbody>
    </table>
</div>
```

---

## 3. Fingerprint & Unit Verification

A critical observation from initial fingerprinting is that while the Customer Charge is presented in **dollars per month ($/month)**, variable delivery charges are displayed in **cents per kilowatt-hour (¢/kWh)**:

| Component Label | Displayed Cell Value | Units | Conversion to USD/kWh | Known Test Fingerprint | Match Status |
|---|---|---|---|---|---|
| **Customer Charge (per month)** | `$19.81` | $/month | Fixed $19.81 | `19.81` | **Exact match** |
| **Distribution Charge (per kWh)** | `6.727` | ¢/kWh | `6.727 / 100 = 0.06727` | `0.06727` | **Exact match** |
| **Regulatory Reconciliation Adjustment (per kWh)** | `0.296` | ¢/kWh | `0.296 / 100 = 0.00296` | `0.00296` | **Exact match** |
| **Pole Plant Adjustment Mechanism (per kWh)** | `-0.029` | ¢/kWh | `-0.029 / 100 = -0.00029` | `-0.00029` | **Exact match** |
| **Transmission Charge** | `4.445` | ¢/kWh | `4.445 / 100 = 0.04445` | `0.04445` | **Exact match** |
| **Stranded Cost Recovery Charge (per kWh)** | `-0.148` | ¢/kWh | `-0.148 / 100 = -0.00148` | `-0.00148` | **Exact match** |
| **System Benefits Charge (per kWh)** | `0.618` | ¢/kWh | `0.618 / 100 = 0.00618` | `0.00618` | **Exact match** |

### Exact Mathematical Summation
$$\begin{aligned}
\text{Total Variable Delivery} &= 0.06727 + 0.00296 - 0.00029 + 0.04445 - 0.00148 + 0.00618 \\
&= \mathbf{0.11909\text{ USD/kWh}}
\end{aligned}$$

$$\begin{aligned}
\text{Total Variable Tariff (Supply + Delivery)} &= 0.14009 + 0.11909 \\
&= \mathbf{0.25918\text{ USD/kWh}}
\end{aligned}$$

---

## 4. Delivery Change Schedule
The page states:
> *"Delivery rates typically change four times a year – on January 1, February 1, August 1 and October 1."*

Unlike the supply page, which provides a single date range header ("August 1, 2026 through January 31, 2027"), delivery components are governed by individual tariff filings approved by the New Hampshire Public Utilities Commission (NHPUC). They are compiled on this page into a single, authoritative live snapshot.

---

## 5. Recommended Extraction Strategy
Extraction should use canonical label matching on the HTML table:

1. Locate any `<table>` element containing both `"Customer Charge"` and `"Distribution Charge"`.
2. Iterate through each `<tr>` and evaluate cell 0 (label) and cell 1 (value).
3. Map labels using case-insensitive canonical keywords:
   - `customer charge` $\rightarrow$ Monthly fixed fee ($)
   - `distribution charge` $\rightarrow$ Variable component (¢/kWh $\rightarrow$ divide by 100)
   - `regulatory reconciliation` $\rightarrow$ Variable component
   - `pole plant adjustment` $\rightarrow$ Variable component (supports negative values)
   - `transmission charge` $\rightarrow$ Variable component
   - `stranded cost recovery` $\rightarrow$ Variable component (supports negative values)
   - `system benefits` $\rightarrow$ Variable component
4. Require all 7 components to be present. If any component is absent, abort calculation and report an error to prevent partial sums.
