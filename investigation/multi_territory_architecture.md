# Eversource multi-territory architecture investigation

Read-only public-source investigation of how Eversource exposes residential
electric tariff content across New Hampshire, Connecticut, and Massachusetts.
No CT/MA production support is claimed or enabled by this document.

Investigation date: 2026-09-05.

## Method

- First-party public HTML fetches via `aiohttp` (no authentication).
- Playwright interaction with Eversource's public location chooser / town
  picker to observe cookies set by Eversource's own UI.
- Comparison of territory-suffixed URLs versus generic URLs with a
  `.SEGMENT` cookie.
- Prior repo notes in `investigation/segment_matrix.md` and
  `investigation/location_resolution.md` were used as leads only; findings
  below are re-checked against live pages.

## Verified public territory identifiers

| Human-readable location | Logical territory key (future) | Public URL suffix observed | `.SEGMENT` observed from UI | PersonalizationKey | Operating company code(s) | Auth required |
|---|---|---|---|---|---|---|
| New Hampshire (Manchester, NH) | `nh` | `/nh` | **`nh`** | `nh` | `PSNH` | No |
| Connecticut (East Hartford, CT) | `ct` | `/ct` | **`ct`** | `ct` | `CLP` | No |
| Eastern Massachusetts (Boston, MA) | `ema` | `/ema` | **`ema`** | `ema` | `NSTAR Electric` | No |
| Western Massachusetts (Springfield, MA) | `wma` | `/wma` | **`wma`** | `wma` | `WMECO` | No |

Notes:

- `.SEGMENT` values above were observed directly in `document.cookie` after
  selecting towns through Eversource's public UI. They are verified.
- Page markup also references `egma` as a selector/config token. Town
  selection for Boston and Springfield set `.SEGMENT=ema` and
  `.SEGMENT=wma` respectively. **`.SEGMENT=egma` was not observed** in this
  session and must not be treated as a verified production segment.
- Additional cookies set by the UI include `.PERSONALIZATION` (JSON with
  town, zip, personalization key, operating company) and `.REGION` (zip /
  state / operating company). Prior NH work showed `.SEGMENT` alone is
  sufficient for NH; this session did not re-prove that for CT/EMA/WMA.

## Public URL families

Base path:

`/residential/account-billing/manage-bill/about-your-bill/rates-tariffs`

Observed working suffixes (HTTP 200, no auth, no cookie required):

| Territory | Hub | Supply | Delivery |
|---|---|---|---|
| NH | `/rates-tariffs/nh` | `/electric-supply-rates/nh` | `/electric-delivery-rates/nh` |
| CT | `/rates-tariffs/ct` | `/electric-supply-rates/ct` | `/electric-delivery-rates/ct` |
| EMA | `/rates-tariffs/ema` | `/electric-supply-rates/ema` | `/electric-delivery-rates/ema` |
| WMA | `/rates-tariffs/wma` | `/electric-supply-rates/wma` | `/electric-delivery-rates/wma` |
| EGMA path | `/rates-tariffs/egma` | present in markup | treated as investigation-only |

Important change versus older notes: earlier investigation concluded paths were
identical across territories and relied solely on `.SEGMENT`. Live pages now
also serve territory-specific content via URL suffixes without cookies.

## Cookie vs suffixed-URL comparison

Tested with unauthenticated `aiohttp` GETs.

### Approach A — generic URL + `Cookie: .SEGMENT=<value>`

| Segment | Supply generic | Delivery generic | Result |
|---|---|---|---|
| `nh` | Rate R fingerprints present (`0.14009`) | Rate R delivery fingerprints present (`19.81`, `6.727`) | Works for NH |
| `ct` | not re-proven on generic delivery | no Rate 1 / Local Delivery fingerprints | **Did not** personalize CT delivery in this probe |
| `ema` | — | no EMA residential delivery fingerprints | **Did not** personalize EMA delivery in this probe |
| `wma` | — | not separately successful on generic delivery | unverified for cookie-only |

### Approach B — territory-suffixed URL, no cookie

| URL | Result |
|---|---|
| `/electric-delivery-rates/nh` | Current Rate R Delivery Rates |
| `/electric-delivery-rates/ct` | Current Rate 1 Delivery Rates; Transmission / Local Delivery / Public Benefits |
| `/electric-delivery-rates/ema` | Residential Non-Heating / Heat Pump / Heating tables |
| `/electric-delivery-rates/wma` | Same structural families as EMA with WMA values |
| `/electric-supply-rates/nh` | Rate R supply |
| `/electric-supply-rates/ct` | Rate 1 / Rate 7 residential supply |
| `/electric-supply-rates/ema` | Basic Service Fixed + Monthly Variable |
| `/electric-supply-rates/wma` | Basic Service Fixed + Monthly Variable (different prices) |

No login wall was encountered for these public pages.

### Recommendation for future fetch strategy

- **Needed now:** keep the existing NH production strategy
  (generic supply/delivery URLs + `.SEGMENT=nh`) unchanged.
- **Likely future:** prefer **territory-suffixed public URLs** for new
  territories because they returned correct content without cookies and
  without auth in this investigation.
- Do not change NH production fetching based solely on this investigation.
- Treat `.SEGMENT` as an implementation detail that may still be useful as a
  secondary signal, especially where URL suffixes and Sitefinity personalization
  interact.

## New Hampshire (supported today)

- Logical territory: `nh`
- Common residential rate class: Rate R (`r`)
- Public suffixes: `/nh`
- Verified segment: `nh`
- Delivery presentation: single current Rate R table with Delivery Component /
  Current Rate columns plus Customer Charge; riders include distribution,
  regulatory reconciliation, pole plant, transmission, stranded cost recovery,
  system benefits.
- Time-of-day: Residential Time-of-Day (ROTOD-2) is linked on the NH delivery
  page but is out of current product scope.

## Connecticut

- Logical territory: `ct`
- Verified segment / URL suffix: `ct`
- Common residential delivery presentation: **Rate 1**
- Public supply page also references Rate 1, Rate 5, Rate 7.
- Hub page advertises **Electric Time of Day Rate 7** and Variable Peak Pricing
  as separate future tariff shapes. Do not implement Rate 7 yet.

### CT delivery page shape (differs from NH)

Observed on `/electric-delivery-rates/ct`:

- Heading: "Current Rate 1 Delivery Rates"
- Semantically separate component groups rather than one NH-style flat rider list:
  - **Transmission** (e.g. Transmission Charge)
  - **Local Delivery** (Distribution Customer Service Charge / Distribution Charge /
    ESI / Revenue Adjustment / Competitive Transition Assessment, etc.)
  - **Public Benefits** section exists in page markers
- Table count observed: 2 HTML tables on the delivery page.
- Customer charge appears as a fixed monthly distribution customer service charge
  (example observed: `$9.62` per month), not the NH `$19.81` Rate R charge.

A future CT parser cannot reuse the NH Rate R component inventory.

## Massachusetts

### EMA vs WMA

Both expose residential delivery families:

- Residential, Non-Heating
- Residential Heat Pump Service
- Residential, Heating

Observed rate-class labels in page content include combinations such as
`R1` / `R2`, `R1HP` / `R2HP`, `R3` / `R4` (and related assistance variants).
Exact product keys are not finalized here.

### Supply plan dimension (future)

EMA and WMA supply pages both describe Residential Basic Service with:

- **Fixed** (default on account open; changes Feb 1 / Aug 1)
- **Monthly Variable** (customer may choose once)

Observed Fixed Basic Service examples on 2026-09-05 (public pages):

| Territory | Feb 1 2026 – Jul 31 2026 | Aug 1 2026 – Jan 31 2027 |
|---|---|---|
| EMA | `$0.15629` / kWh | `$0.17323` / kWh |
| WMA | `$0.13683` / kWh | `$0.15934` / kWh |

This confirms EMA and WMA have **different** residential Basic Service supply
pricing. Supply plan should be modeled as a future independent dimension from
delivery rate class.

### Heat-pump / seasonal delivery

EMA/WMA heat-pump tables include seasonal distribution energy charges
(Summer May–October vs Winter November–April). Any future heat-pump support
needs seasonal component handling.

### Massachusetts service-area concepts

Observed on EMA delivery pages:

- Energy Efficiency Charge (**Greater Boston, Cambridge and South Shore only**)
- Energy Efficiency Charge (**Cape Cod and Martha's Vineyard only**)

WMA delivery page showed a single Energy Efficiency Charge line in the sampled
rows (no Cape dual-rate split in the WMA sample).

Tariff literature / page text also references service-area tokens such as
`BOST`, `CAMB`, `SOUTH`, `CAPE`, plus territory keys `EMA` / `WMA`.

Material pricing impact for residential all-in variable delivery:

| Concept | Affects all-in variable $/kWh? | Notes |
|---|---|---|
| EMA vs WMA | Yes | Different Basic Service supply; separate delivery pages |
| CAPE vs BOST/CAMB/SOUTH (within EMA) | Yes for delivery EE charge | Dual Energy Efficiency rates on EMA delivery page |
| Delivery rate family (R1/R2 vs R1HP/R2HP vs R3/R4) | Yes | Different tables / seasonal components |
| Fixed vs Monthly Variable supply | Yes | Independent supply-plan choice |
| `egma` selector token | Unknown | Present in markup; not UI-verified as `.SEGMENT` |

Do not infer HA config support from naming alone.

## Model recommendation

### Needed now (for architecture PRs without enabling CT/MA)

- `territory` key (logical integration identity; today only `nh`)
- display name
- Sitefinity `segment` (implementation detail; today `nh`)
- `supported_rate_classes`
- delivery rate class key
- collision-safe entity object IDs that include territory + rate class for
  non-legacy combinations

### Likely future (when a real supported tariff requires them)

- public URL suffix (may equal segment for NH/CT/EMA/WMA today, but keep
  separate fields so they can diverge)
- Massachusetts service area / subarea (`BOST` / `CAMB` / `SOUTH` / `CAPE`)
- supply plan (`fixed` / `monthly_variable` / third-party manual)
- territory-specific parser strategies and component inventories
- seasonal delivery component windows

### Investigation-only

- `egma` until observed as an actual `.SEGMENT` from Eversource UI
- Rate 7 / Variable Peak Pricing / ROTOD-2 implementations
- authenticated account-linked personalization beyond public pages

## Implications for upcoming engineering PRs

1. Preserve NH Rate R entity IDs exactly.
2. Separate logical `territory` from `segment` in the HTTP client.
3. Do not add CT/EMA/WMA to production `TERRITORIES` or the config-flow UI yet.
4. Prefer documenting URL-suffix fetch as the future default while leaving NH's
   proven cookie strategy alone for now.
5. Expect CT and MA parsers to be structurally different from NH Rate R.

## Unknowns requiring another DevTools pass

1. Why CT/EMA `.SEGMENT` cookies alone failed to personalize generic delivery
   URLs in the unauthenticated probe while NH succeeded.
2. Whether `.REGION` / `.PERSONALIZATION` become required companions for
   non-NH segments.
3. Exact mapping of every MA town to `ema` vs `wma` vs any `egma` path.
4. Whether CAPE subarea is selectable as its own personalization key or only
   as a delivery-table footnote within EMA.
5. Stable machine keys for CT Rate 1 / Rate 7 and MA R1/R1HP families suitable
   for Home Assistant config entries.
