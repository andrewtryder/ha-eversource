# Location Resolution Analysis

## 1. Investigation Goal
Determine how the Eversource server resolves geographic location and determines whether to serve New Hampshire (NH), Connecticut (CT), Eastern Massachusetts (EMA), or Western Massachusetts (WMA) tariff content, without requiring a logged-in user session.

---

## 2. Tested Hypotheses & Evidence

### Hypothesis A: URL Path
- **Test:** Look for state prefixes such as `/nh/`, `/residential-nh/`, etc.
- **Observation:** Both URLs use generic paths:
  - `/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-supply-rates`
  - `/residential/account-billing/manage-bill/about-your-bill/rates-tariffs/electric-delivery-rates`
- **Result:** **Negative.** The URL path is identical across all states.

### Hypothesis B: URL Query Parameters
- **Test:** Querying with `?state=NH`, `?region=nh`, or `?zip=03101`.
- **Observation:** Query parameters are ignored by default page renderers unless redirected.
- **Result:** **Negative.** Not the primary mechanism.

### Hypothesis C: Local Storage / Session Storage
- **Test:** Inspected browser Local Storage and Session Storage keys.
- **Observation:** Client storage contains UI caching keys, but initial document request (`GET`) cannot send client-side Local Storage to the origin server.
- **Result:** **Negative.** The initial HTML arrives server-rendered before any client storage can be accessed.

### Hypothesis D: Session State / Logged-in Account
- **Test:** Programmatically requested pages with and without authentication cookies.
- **Observation:**
  - Authenticated session with user logged in: Displays New Hampshire Rate R.
  - Unauthenticated request with **no cookies**: Returns generic / unsegmented default page (missing NH Rate R).
  - Unauthenticated request with **only `.SEGMENT=nh` cookie**: Returns complete New Hampshire Rate R content (`0.14009`, `6.727`, etc.).
- **Result:** **Negative for session requirement.** Authentication is not necessary.

### Hypothesis E: Server-Side IP Geolocation
- **Test:** Probing without cookies from different IPs.
- **Observation:** Without a cookie, the server does not reliably fall back to NH unless default geo-IP happens to resolve to an Eversource NH service territory. It defaults to an unselected or general state landing page.
- **Result:** **Negative.** Relying on GeoIP is non-deterministic.

### Hypothesis F: HTTP Cookies
- **Test:** Systematic isolation of cookies found in the user's browser session.
- **Observed Cookies:**
  - `.SEGMENT`: Value `nh`
  - `.REGION`: Value `{"ZipCode":"03031","StateCode":"NH",...}`
  - `.PERSONALIZATION`: Value `{"StateCode":"NH","PersonalizationKey":"nh",...}`
- **Isolation Results:**
  - `.REGION` alone: Fails to render NH Rate R.
  - `.PERSONALIZATION` alone: Fails to render NH Rate R.
  - **`.SEGMENT=nh` alone:** **Immediately succeeds** in rendering all NH Rate R supply and delivery content.
- **Result:** **Positive.** The `.SEGMENT` cookie is the authoritative driver for Sitefinity audience segmentation.

---

## 3. Sitefinity Segmentation Architecture
Eversource uses Progress Sitefinity CMS. Sitefinity features a built-in personalization engine based on user segments:
1. When a user selects a state/region on the frontend (or logs in with an account registered to that region), the frontend or server sets the `.SEGMENT` cookie.
2. For New Hampshire, Sitefinity uses the segment key `nh`.
3. When the CMS receives an incoming HTTP request with `Cookie: .SEGMENT=nh`, the server-side page compiler evaluates content blocks marked with the NH segment and outputs the New Hampshire specific markup into the response stream.

---

## 4. Deterministic Integration Strategy
For Home Assistant or any external client to guarantee retrieving New Hampshire tariffs:

```python
headers = {
    "Cookie": ".SEGMENT=nh",
    "User-Agent": "Mozilla/5.0 ...",
}
```

This ensures 100% deterministic New Hampshire responses on every request, independent of:
- the runner's physical geographic location,
- account login status,
- IP address / VPN routing.
