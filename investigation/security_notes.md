# Security and Privacy Notes

## 1. Compliance with Privacy & Security Guidelines
Throughout this investigation:
- **Zero Account Modifications:** No account state was modified. No forms, settings, or payment details were submitted.
- **Zero Credential Exposure:** No passwords, session cookies, bearer tokens, or CSRF verification tokens were captured, logged, or saved in any repository artifact.
- **Zero PII Exposure:** No customer names, account numbers, physical addresses, or financial data are included in test fixtures, source code, or documentation.
- **Public Fixtures Only:** All fixtures saved in `tests/fixtures/` were retrieved via clean, unauthenticated HTTP requests without a logged-in user profile.

---

## 2. Authentication & Authorization Assessment

### Finding: Rate Data Is Inherently Public
Electricity utilities in regulated markets (such as New Hampshire, regulated by the NHPUC) are legally required to publish standard default service supply rates and delivery tariffs. 

- **Rate R** is the standard, default tariff schedule available to any residential electric customer in Eversource's New Hampshire service territory.
- Because it is a public tariff of general applicability, Eversource makes the data accessible on public web pages without requiring customer authentication or account registration.

### Finding: No Session Tokens or Secrets in Integration
The planned Home Assistant integration requires **NO** credentials:
- No Eversource username or password.
- No OAuth2 / client credentials.
- No session cookie harvesting.
- No API keys.

The only header required is the public segmentation flag:
```http
Cookie: .SEGMENT=nh
```
This flag is an audience filter indicating geographic interest in New Hampshire content, containing no identifying information.

---

## 3. Rate Limiting, Polling Hygiene & Network Safety

1. **Infrequent Update Cadence:**
   - Supply rates change only twice per year (February 1 and August 1).
   - Delivery components typically change four times per year (January 1, February 1, August 1, October 1).
   - The Home Assistant integration should poll **at most once every 6 to 12 hours** (or daily), with an option for manual reload.
   - This translates to ~2–4 requests per day, placing virtually zero load on Eversource web servers.

2. **Respect for Origin Servers:**
   - Use standard User-Agent strings.
   - Do not bypass Cloudflare/Akamai or aggressive scraping protections (none were encountered under normal unauthenticated GET requests).
   - Do not open unnecessary concurrent connections.

3. **User Privacy in Home Assistant:**
   - Because the integration is purely public and unauthenticated, users of the HACS integration never have to trust Home Assistant with their Eversource utility account credentials.
   - There is zero risk of credential leaks, session hijacking, or unauthorized account modifications through this integration.
