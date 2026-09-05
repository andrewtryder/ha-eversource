# Candidate Endpoints & Architectural Ranking

## 1. Candidate Inventory

During the investigation, several candidate paths were examined as potential sources for electricity rates:

| Candidate ID | Name / Description | URL / Path | Format | Auth Required? |
|---|---|---|---|---|
| **C1** | Server-Rendered Supply Page | `/residential/.../rates-tariffs/electric-supply-rates` | HTML | **No** (with `.SEGMENT=nh`) |
| **C2** | Server-Rendered Delivery Page | `/residential/.../rates-tariffs/electric-delivery-rates` | HTML Table | **No** (with `.SEGMENT=nh`) |
| **C3** | Personalization API | `/RestApi/personalizations/render` | JSON | No (but lacks rates) |
| **C4** | Published Summary PDF | `/docs/default-source/rates-tariffs/nh-summary-rates.pdf` | PDF Document | **No** (Public static PDF) |
| **C5** | Authenticated Customer API | `/cg/customer/...` | JSON | **Yes** (Session / OAuth) |

---

## 2. Assessment & Robustness Hierarchy

We evaluate each approach according to our robustness hierarchy:

### Rank 1: Structured Public JSON API
- **Status on Eversource:** **Does not exist.**
- **Evaluation:** Eversource does not expose a dedicated public REST/JSON endpoint for tariff data.

### Rank 2: Structured Public HTML Table
- **Applicability:** **Applies to Delivery Rates (Candidate C2).**
- **Evaluation:** The delivery page renders an HTML table (`table.table-striped.k-table`) with standard headers (`Delivery Component`, `Current Rate`). Rows are labeled with clear semantic strings (`Customer Charge`, `Distribution Charge`, `Transmission Charge`, etc.).
- **Robustness:** **High.** HTML table parsers targeting semantic row labels are resilient against layout styling changes and minor markup adjustments.

### Rank 3: Semantically Identifiable Server-Rendered HTML
- **Applicability:** **Applies to Supply Rates (Candidate C1).**
- **Evaluation:** The supply page renders a content block with a distinct heading (`<h2>Current Supply Rates</h2>`) followed by a paragraph containing `"The supply rate for Rate R will be $0.14009 per kWh August 1, 2026 through January 31, 2027."`
- **Robustness:** **High.** A regex pattern anchored on `Rate R will be $<val> per kWh` reliably extracts the value and effective dates without depending on fragile CSS positional selectors.

### Rank 4: Published Tariff PDF Document
- **Applicability:** `/docs/default-source/rates-tariffs/nh-summary-rates.pdf?sfvrsn=eefadaef_44`
- **Evaluation:** Eversource links to a PDF summary on both supply and delivery pages.
- **Robustness:** **Medium-Low.** PDFs require heavyweight dependencies (`pdfminer`, `pypdf`), have complex tabular layout extraction rules, and the query parameter `sfvrsn=...` or file path can change when a new revision is uploaded.

### Rank 5: Personalized Endpoint
- **Applicability:** `/RestApi/personalizations/render`
- **Evaluation:** **Fails.** As established in `personalization_findings.md`, this endpoint only serves navigational header chrome and does not contain tariff numbers.

### Rank 6: DOM Scraping by CSS Position
- **Evaluation:** **Do NOT use.** Selectors like `div:nth-child(4) > div:nth-child(2) > p` break whenever a banner, disclaimer, or header is added.

### Rank 7: Browser Automation
- **Evaluation:** **Do NOT use.** Running Playwright, Puppeteer, or Selenium inside Home Assistant introduces severe memory overhead, CPU consumption, and ongoing stability issues.

---

## 3. Final Recommended Strategy

Combine **Candidate C1** (for Supply) and **Candidate C2** (for Delivery) via an unauthenticated, asynchronous HTTP client (`aiohttp`):
1. **Supply:** GET `.../electric-supply-rates` with `Cookie: .SEGMENT=nh` $\rightarrow$ Parse Rate R text and effective dates.
2. **Delivery:** GET `.../electric-delivery-rates` with `Cookie: .SEGMENT=nh` $\rightarrow$ Parse semantic table rows, normalize ¢/kWh to USD/kWh, and calculate total variable rate + monthly fixed charge.
