# Personalization Endpoint Findings

## 1. Context & Background
During prior manual exploration of the Eversource web application, an endpoint resembling `/RestApi/personalizations/render` (or `/RestApi/personalisations/render`) was observed returning personalized controls, including the New Hampshire region selector and navigation.

The goal of Phase 5 was to determine whether this endpoint delivers the underlying electricity tariff rates or merely client-side chrome.

---

## 2. Endpoint Inspection & Evidence

### Request Details
- **Observed URL:**
  `https://www.eversource.com/RestApi/personalizations/render?pageNodeId=<guid>&pageDataId=<guid>&pageNodeKey=<guid>&url=<path>&controls=<guid-list>&correlationId=<guid>`
- **Method:** `GET`
- **Response Format:** JSON array of control payload objects.

### Observed Payload Analysis
The network trace captured the full response payload of this request during page load:

```json
[
  {
    "ControlId": "dcfb6ea8-7aaa-438f-80b4-7dd24ac482b2",
    "Content": "<div class=\"header-crown--desktop\" id=\"dt-headercrown-d\">\r\n <div class=\"header-container\">\r\n <div class=\"header-container header-crown__items\">\r\n <ul class=\"header-crown__switch-site\">\r\n <li class=\"header-crown__switch-site-item\">Residential</li>\r\n <li class=\"header-crown__switch-site-item\"><a href=\"https://www.eversource.com/business\">Switch to Business Site</a></li>\r\n </ul>\r\n <div class=\"header-crown__right-items\">\r\n <label id=\"region-dropdown2-label\" class=\"c-region-dropdown__label u-sr-only\">New Hampshire</label>\r\n <div class=\"c-region-dropdown js-region-dropdown-2\">\r\n <div data-placeholder-regiontext aria-controls=\"region-dropdown-listbox2\" aria-expanded=\"false\" ...>New Hampshire</div>\r\n ...\r\n"
  }
]
```

### Evaluation Against Known Tariff Fingerprints
A comprehensive substring search was conducted across the returned payload for all known test values:
- `0.14009`: **Not found**
- `0.06727` / `6.727`: **Not found**
- `0.00296` / `0.296`: **Not found**
- `0.04445` / `4.445`: **Not found**
- `19.81`: **Not found**

**Result:** Zero tariff values appear in any control returned by this endpoint.

---

## 3. What the Control IDs Represent
- **ControlId `dcfb6ea8-7aaa-438f-80b4-7dd24ac482b2`:** The top header desktop navigation bar (`header-crown--desktop`), which includes:
  - Residential / Business portal switcher
  - State region dropdown selector (`js-region-dropdown-2`) displaying "New Hampshire"
  - Sign-in / My Account navigation entry points

---

## 4. Operational Characteristics
1. **Authentication Requirement:** The endpoint does not strictly require authentication, but it expects Sitefinity internal routing parameters (`pageNodeId`, `pageDataId`, `pageNodeKey`, etc.).
2. **State / Town Dependence:** The content returned inside the header reflects the active state selection (e.g. New Hampshire).
3. **Hydration Role:** The client-side script parses this JSON and replaces corresponding placeholder elements in the DOM with the HTML strings contained in the `Content` property.

---

## 5. Architectural Recommendation
> [!CAUTION]
> **DO NOT USE THE PERSONALIZATION ENDPOINT IN THE HOME ASSISTANT INTEGRATION.**

### Reasons:
1. **Zero Tariff Data:** The endpoint does not supply tariff figures.
2. **Brittle Parameters:** It relies on opaque Sitefinity internal CMS GUIDs (`pageNodeId`, `pageDataId`) that can change on any CMS page republish.
3. **Unnecessary Complexity:** The tariff data is already fully present in the main document response before this XHR is ever initiated.
