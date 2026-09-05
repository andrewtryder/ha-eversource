# Network Request Inventory

## Overview
This document inventories network activity observed during browser navigation and programmatic probing of the Eversource electricity supply and delivery pages:
- Supply URL: `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates`
- Delivery URL: `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates`

All network records have been sanitized in accordance with privacy rules (authentication tokens, CSRF tokens, session IDs, and PII are excluded).

---

## Detailed Request Inventory

### 1. Main Document — Electric Supply Rates
- **URL:** `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates`
- **HTTP Method:** `GET`
- **Response Status:** `200 OK`
- **Content-Type:** `text/html; charset=utf-8`
- **Initiator:** Browser navigation / document parser
- **Query Parameter Names:** None
- **Timing:** Initial request (pre-personalization XHR)
- **Contains Known Fingerprints:**
  - `0.14009` (USD/kWh)
  - `Rate R`
  - `Current Supply Rates`
  - `August 1, 2026 through January 31, 2027`
- **Endpoint Classification:** **PUBLIC** (when sent with `.SEGMENT=nh` cookie; no session or login required).
- **Format:** HTML (Sitefinity CMS server-side rendered document).
- **Response Length:** ~206 KB.

---

### 2. Main Document — Electric Delivery Rates
- **URL:** `https://www.eversource.com/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates`
- **HTTP Method:** `GET`
- **Response Status:** `200 OK`
- **Content-Type:** `text/html; charset=utf-8`
- **Initiator:** Browser navigation / document parser
- **Query Parameter Names:** None
- **Timing:** Initial request (pre-personalization XHR)
- **Contains Known Fingerprints:**
  - `19.81` (Customer Charge)
  - `6.727` (Distribution Charge in ¢/kWh)
  - `0.296` (Regulatory Reconciliation Adjustment in ¢/kWh)
  - `-0.029` (Pole Plant Adjustment Mechanism in ¢/kWh)
  - `4.445` (Transmission Charge in ¢/kWh)
  - `-0.148` (Stranded Cost Recovery Charge in ¢/kWh)
  - `0.618` (System Benefits Charge in ¢/kWh)
- **Endpoint Classification:** **PUBLIC** (when sent with `.SEGMENT=nh` cookie; no session or login required).
- **Format:** HTML (Sitefinity CMS server-side rendered table inside `sfContentBlock`).
- **Response Length:** ~208 KB.

---

### 3. Personalization Render API
- **URL:** `https://www.eversource.com/RestApi/personalizations/render`
- **HTTP Method:** `GET`
- **Response Status:** `200 OK`
- **Content-Type:** `application/json; charset=utf-8`
- **Initiator:** Script (`Eversource.Sitefinity.Frontend` personalization client)
- **Query Parameter Names:**
  - `pageNodeId`
  - `pageDataId`
  - `pageNodeKey`
  - `url`
  - `controls`
  - `correlationId`
- **Timing:** Post-load XHR (triggered ~300ms after DOMContentLoaded)
- **Contains Known Fingerprints:** **NONE.** Searched for all tariff fingerprints (`0.14009`, `6.727`, `19.81`, etc.) with zero hits.
- **Endpoint Classification:** Hybrid / Internal CMS control renderer.
- **Format:** JSON array of control objects `[{"ControlId": "...", "Content": "..."}]`.
- **Payload Purpose:** Injects header region dropdown, user sign-in/sign-out buttons, and navigation controls. Does not render or manage tariff content.

---

### 4. Legacy Home URL Configuration
- **URL:** `https://www.eversource.com/Eversource.Sitefinity.Frontend/Legacy/home-url.json`
- **HTTP Method:** `GET`
- **Response Status:** `200 OK`
- **Content-Type:** `application/json`
- **Initiator:** Parser / static resource
- **Query Parameter Names:** None
- **Contains Known Fingerprints:** None.
- **Endpoint Classification:** Public static asset.
- **Payload Purpose:** Maps basic domain routing paths.

---

### 5. Interstitial Message Service
- **URL:** `https://www.eversource.com/esapi/page-piece/interstitial`
- **HTTP Method:** `GET`
- **Response Status:** `200 OK`
- **Content-Type:** `application/json; charset=utf-8`
- **Initiator:** Script
- **Query Parameter Names:** None
- **Contains Known Fingerprints:** None.
- **Endpoint Classification:** Public messaging endpoint.
- **Payload Purpose:** Checks whether modal alerts or notifications should be displayed to the user.

---

## Comparative Assessment: Document vs. REST API

| Property | Main Document HTML (`GET /...rates`) | Personalization API (`/RestApi/...`) |
|---|---|---|
| **Contains Tariff Rates?** | **YES (Complete set)** | **NO (0 hits)** |
| **Dependencies** | Plain HTTP `GET` with `.SEGMENT=nh` cookie | 6 query parameters (`pageNodeId`, `pageDataId`, etc.) |
| **Authentication** | None required | None required (but state-specific) |
| **Parsing Complexity** | Low (semantic table + regex) | Not applicable |
| **Risk of Breaking** | Low (standard CMS publishing template) | High (internal CMS RPC endpoint) |
| **Recommendation** | **PRIMARY SOURCE** | **DO NOT USE** |
