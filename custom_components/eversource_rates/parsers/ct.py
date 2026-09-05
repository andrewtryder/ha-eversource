"""Connecticut Rate 1 public tariff parsers."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from ..models import DeliveryComponent, DeliveryRates, SupplyRate
from .common import (
    EversourceParseError,
    component_key,
    decimal,
    is_summary_row,
    parse_cell,
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_PERIOD_PATTERN = re.compile(
    r"([A-Za-z]+)\.?\s+(\d{1,2})\s*[-–—]\s*([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_RATE_1_ROW = re.compile(r"\brate\s*1\b", re.IGNORECASE)
_CUSTOMER_CHARGE_LABELS = (
    "distribution customer service charge",
    "customer service charge",
    "customer charge",
)
_REQUIRED_VARIABLE = frozenset({"transmission_charge", "distribution_charge"})


def _parse_month_day_year(month: str, day: str, year: str) -> date:
    month_key = month.lower().rstrip(".")
    if month_key not in _MONTHS:
        raise EversourceParseError(f"Unrecognized month in supply period: {month!r}")
    try:
        return date(int(year), _MONTHS[month_key], int(day))
    except ValueError as err:
        raise EversourceParseError(
            f"Malformed supply period date: {month} {day}, {year}"
        ) from err


def _parse_period_header(header: str) -> tuple[date, date]:
    match = _PERIOD_PATTERN.search(" ".join(header.split()))
    if match is None:
        raise EversourceParseError(f"Malformed CT supply period header: {header!r}")
    start = _parse_month_day_year(match.group(1), match.group(2), match.group(5))
    end = _parse_month_day_year(match.group(3), match.group(4), match.group(5))
    if end < start:
        raise EversourceParseError(f"Inverted CT supply period: {header!r}")
    return start, end


def _select_current_period(
    headers: list[str], *, today: date
) -> tuple[int, date, date]:
    """Pick the single supply column whose inclusive date range contains today."""
    matches: list[tuple[int, date, date]] = []
    for index, header in enumerate(headers):
        start, end = _parse_period_header(header)
        if start <= today <= end:
            matches.append((index, start, end))
    if not matches:
        raise EversourceParseError(
            f"No CT Rate 1 supply period covers {today.isoformat()}"
        )
    if len(matches) > 1:
        raise EversourceParseError("Ambiguous overlapping CT Rate 1 supply periods")
    return matches[0]


def _find_supply_table(soup: BeautifulSoup) -> Tag:
    heading = next(
        (
            h
            for h in soup.find_all(["h1", "h2", "h3"])
            if "current residential supply rates" in h.get_text(" ", strip=True).lower()
            or "current supply rates" in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is None:
        raise EversourceParseError(
            "Could not locate CT Rate 1 supply "
            "(Current Residential Supply Rates missing)"
        )
    table = next(
        (t for t in heading.find_all_next("table") if t.find("th")),
        None,
    )
    if table is None:
        raise EversourceParseError("Could not locate CT residential supply table")
    return table


def _find_rate_1_supply_row(table: Tag) -> list[Tag]:
    rate_row = None
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = " ".join(cells[0].get_text(" ", strip=True).split())
        if _RATE_1_ROW.search(label):
            if rate_row is not None:
                raise EversourceParseError("Conflicting CT Rate 1 supply rows")
            rate_row = cells
    if rate_row is None:
        raise EversourceParseError("Could not locate Rate 1 supply row")
    return rate_row


def parse_supply_html(
    html: str, rate_class: str = "1", *, today: date | None = None
) -> SupplyRate:
    """Extract CT Rate 1 / Standard Service from the residential supply table."""
    if rate_class != "1":
        raise EversourceParseError(
            f"Unsupported supply rate class for CT Rate 1 parser: {rate_class!r}"
        )
    as_of = today or date.today()
    table = _find_supply_table(BeautifulSoup(html, "html.parser"))

    header_cells = table.find("tr")
    if header_cells is None:
        raise EversourceParseError("CT supply table is missing a header row")
    headers = [
        " ".join(cell.get_text(" ", strip=True).split())
        for cell in header_cells.find_all(["th", "td"])
    ]
    if len(headers) < 2:
        raise EversourceParseError("CT supply table is missing period columns")
    column_index, start, end = _select_current_period(headers[1:], today=as_of)

    rate_row = _find_rate_1_supply_row(table)
    if len(rate_row) < column_index + 2:
        raise EversourceParseError("CT Rate 1 supply row is missing the current period")
    cents_text = " ".join(rate_row[column_index + 1].get_text(" ", strip=True).split())
    cents = decimal(cents_text, "CT Rate 1 supply rate")
    rate = cents / Decimal("100")
    if not Decimal("0") < rate < Decimal("1"):
        raise EversourceParseError(f"Supply rate outside plausible range: {rate}")
    return SupplyRate(rate, start, end, rate_class)


def _is_customer_charge_label(label: str) -> bool:
    normalized = " ".join(label.lower().split())
    return any(phrase in normalized for phrase in _CUSTOMER_CHARGE_LABELS)


def _rate_1_delivery_tables(soup: BeautifulSoup) -> list[Tag]:
    heading = next(
        (
            h
            for h in soup.find_all(["h1", "h2", "h3"])
            if "current rate 1 delivery" in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is None:
        raise EversourceParseError(
            "Could not locate Current Rate 1 Delivery Rates section"
        )
    tables: list[Tag] = []
    for element in heading.find_all_next():
        if isinstance(element, Tag) and element.name in {"h1", "h2"}:
            break
        if isinstance(element, Tag) and element.name == "table":
            tables.append(element)
    if not tables:
        raise EversourceParseError(
            "Could not locate Rate 1 delivery tables near Current Rate 1 Delivery Rates"
        )
    return tables


def _row_label_and_value(cells: list[Tag]) -> tuple[str, str] | None:
    texts = [" ".join(cell.get_text(" ", strip=True).split()) for cell in cells]
    if len(texts) < 2:
        return None
    # Prefer first column as semantic component name; last column as the rate.
    return texts[0], texts[-1]


def parse_delivery_html(html: str) -> DeliveryRates:  # noqa: C901
    """Extract CT Rate 1 Transmission / Local Delivery / Public Benefits rows."""
    soup = BeautifulSoup(html, "html.parser")
    tables = _rate_1_delivery_tables(soup)
    customer_charge: Decimal | None = None
    components: dict[str, DeliveryComponent] = {}
    summary_amount: Decimal | None = None

    for table in tables:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            parsed = _row_label_and_value(cells)
            if parsed is None:
                continue
            label, value = parsed
            amount, unit = parse_cell(value, label)
            if _is_customer_charge_label(label):
                if unit != "USD/month":
                    raise EversourceParseError(
                        "Customer charge is not a monthly dollar value"
                    )
                if customer_charge is not None and customer_charge != amount:
                    raise EversourceParseError("Conflicting values for Customer Charge")
                customer_charge = amount
                continue
            if unit != "USD/kWh":
                raise EversourceParseError(
                    f"Unsupported CT delivery unit for {label}: {value!r}"
                )
            if is_summary_row(label):
                if summary_amount is not None and summary_amount != amount:
                    raise EversourceParseError(
                        "Conflicting delivery summary/total row values"
                    )
                summary_amount = amount
                continue
            key = component_key(label)
            # Prefer stable short keys for the two required components.
            lowered = " ".join(label.lower().split())
            if "transmission charge" in lowered:
                key = "transmission_charge"
            elif lowered.startswith("distribution charge") or lowered == (
                "distribution charge"
            ):
                key = "distribution_charge"
            existing = components.get(key)
            if existing is not None and existing.rate != amount:
                raise EversourceParseError(
                    f"Conflicting values for delivery component {key}"
                )
            components[key] = DeliveryComponent(key, label, amount)

    if customer_charge is None:
        raise EversourceParseError("Missing Customer Charge in CT Rate 1 delivery")
    if not Decimal("0") < customer_charge < Decimal("200"):
        raise EversourceParseError(
            f"Customer charge outside plausible range: {customer_charge}"
        )
    missing = _REQUIRED_VARIABLE - components.keys()
    if missing:
        raise EversourceParseError(
            f"Missing required CT Rate 1 delivery components: {sorted(missing)}"
        )
    parsed = DeliveryRates(customer_charge, components)
    if not Decimal("0") < parsed.variable_rate < Decimal("1"):
        raise EversourceParseError(
            f"Delivery rate outside plausible range: {parsed.variable_rate}"
        )
    if summary_amount is not None and summary_amount != parsed.variable_rate:
        raise EversourceParseError(
            "Delivery summary/total conflicts with component sum: "
            f"{summary_amount} != {parsed.variable_rate}"
        )
    return parsed
