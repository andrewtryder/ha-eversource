"""Massachusetts R1 residential public tariff parsers (EMA / WMA)."""

from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from ..models import DeliveryComponent, DeliveryRates, SupplyRate
from ..tariffs import TariffSelection
from .common import (
    EversourceParseError,
    component_key,
    decimal,
    is_summary_row,
    parse_cell,
)

_FIXED_PERIOD = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+through\s+"
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s*[-–—]\s*\$([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_MONTHLY_PERIOD = re.compile(
    r"([A-Za-z]+)\s+(\d{4})\s*[-–—]\s*\$([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_MONTHS = {
    name.lower(): index for index, name in enumerate(calendar.month_name) if name
} | {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}
_REQUIRED_VARIABLE = frozenset(
    {
        "distribution_energy_charge",
        "transmission_charge",
        "energy_efficiency_charge",
    }
)


def _parse_month(token: str) -> int:
    key = token.lower().rstrip(".")
    if key not in _MONTHS:
        raise EversourceParseError(f"Unrecognized month in MA supply period: {token!r}")
    return _MONTHS[key]


def _section_after_heading(soup: BeautifulSoup, title: str) -> Tag:
    heading = next(
        (
            h
            for h in soup.find_all(["h2", "h3", "h4"])
            if title in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is None:
        raise EversourceParseError(f"Could not locate MA supply section: {title}")
    return heading


def _iter_section_text(heading: Tag) -> str:
    chunks: list[str] = []
    for element in heading.find_all_next():
        if isinstance(element, Tag) and element.name in {"h2", "h3", "h4"}:
            break
        if isinstance(element, Tag) and element.name in {"li", "p"}:
            chunks.append(element.get_text(" ", strip=True))
    return "\n".join(chunks)


def _parse_fixed_supply(html: str, rate_class: str, *, today: date) -> SupplyRate:
    soup = BeautifulSoup(html, "html.parser")
    heading = _section_after_heading(soup, "fixed rate")
    text = _iter_section_text(heading)
    matches = list(_FIXED_PERIOD.finditer(text))
    if not matches:
        raise EversourceParseError("Could not locate MA Fixed Basic Service periods")
    selected = None
    for match in matches:
        start = date(
            int(match.group(3)),
            _parse_month(match.group(1)),
            int(match.group(2)),
        )
        end = date(
            int(match.group(6)),
            _parse_month(match.group(4)),
            int(match.group(5)),
        )
        if end < start:
            raise EversourceParseError("Inverted MA Fixed Basic Service period")
        if start <= today <= end:
            if selected is not None:
                raise EversourceParseError(
                    "Ambiguous overlapping MA Fixed Basic Service periods"
                )
            rate = decimal(match.group(7), "MA Fixed Basic Service rate")
            selected = SupplyRate(rate, start, end, rate_class)
    if selected is None:
        raise EversourceParseError(
            f"No MA Fixed Basic Service period covers {today.isoformat()}"
        )
    if not Decimal("0") < selected.rate < Decimal("1"):
        raise EversourceParseError(
            f"Supply rate outside plausible range: {selected.rate}"
        )
    return selected


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _parse_monthly_variable_supply(
    html: str, rate_class: str, *, today: date
) -> SupplyRate:
    soup = BeautifulSoup(html, "html.parser")
    heading = _section_after_heading(soup, "monthly variable rate")
    text = _iter_section_text(heading)
    matches = list(_MONTHLY_PERIOD.finditer(text))
    if not matches:
        raise EversourceParseError(
            "Could not locate MA Monthly Variable Basic Service rates"
        )
    selected = None
    for match in matches:
        year = int(match.group(2))
        month = _parse_month(match.group(1))
        start, end = _month_bounds(year, month)
        if start <= today <= end:
            if selected is not None:
                raise EversourceParseError(
                    "Ambiguous overlapping MA Monthly Variable periods"
                )
            rate = decimal(match.group(3), "MA Monthly Variable Basic Service rate")
            selected = SupplyRate(rate, start, end, rate_class)
    if selected is None:
        raise EversourceParseError(
            f"No MA Monthly Variable period covers {today.isoformat()}"
        )
    if not Decimal("0") < selected.rate < Decimal("1"):
        raise EversourceParseError(
            f"Supply rate outside plausible range: {selected.rate}"
        )
    return selected


def parse_supply_html(
    html: str,
    selection: TariffSelection,
    *,
    today: date | None = None,
) -> SupplyRate:
    """Extract MA Basic Service supply for the selected plan."""
    if selection.rate_class != "r1":
        raise EversourceParseError(
            f"Unsupported MA supply rate class: {selection.rate_class!r}"
        )
    if selection.supply_plan not in {"fixed", "monthly_variable"}:
        raise EversourceParseError(
            f"Unsupported MA supply plan: {selection.supply_plan!r}"
        )
    as_of = today or date.today()
    if selection.supply_plan == "fixed":
        return _parse_fixed_supply(html, selection.rate_class, today=as_of)
    return _parse_monthly_variable_supply(html, selection.rate_class, today=as_of)


def _find_non_heating_table(soup: BeautifulSoup) -> Tag:
    heading = next(
        (
            h
            for h in soup.find_all(["h2", "h3", "h4"])
            if "residential, non-heating" in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is None:
        raise EversourceParseError(
            "Could not locate Residential, Non-Heating delivery section"
        )
    table = heading.find_next("table")
    if table is None:
        raise EversourceParseError(
            "Could not locate Residential, Non-Heating delivery table"
        )
    return table


def _normalize_ee_key(label: str, service_area: str | None) -> str | None:
    """Return energy_efficiency_charge, skip, or None for non-EE labels."""
    lowered = " ".join(label.lower().split())
    if "energy efficiency" not in lowered:
        return None
    if "cape cod" in lowered or "martha" in lowered:
        return "energy_efficiency_charge" if service_area == "cape" else None
    if (
        "greater boston" in lowered
        or "cambridge" in lowered
        or "south shore" in lowered
    ):
        return "energy_efficiency_charge" if service_area in {None, "main"} else None
    # Undifferentiated EE line (WMA): always include.
    return "energy_efficiency_charge"


def _stable_component_key(label: str) -> str:
    lowered = " ".join(label.lower().split())
    cleaned = re.sub(r"\*+$", "", lowered).strip()
    if cleaned.startswith("distribution energy charge"):
        return "distribution_energy_charge"
    if cleaned.startswith("transmission charge"):
        return "transmission_charge"
    return component_key(cleaned)


def parse_delivery_html(  # noqa: C901
    html: str,
    selection: TariffSelection,
) -> DeliveryRates:
    """Extract MA R1 Residential Non-Heating delivery components."""
    if selection.rate_class != "r1":
        raise EversourceParseError(
            f"Unsupported MA delivery rate class: {selection.rate_class!r}"
        )
    soup = BeautifulSoup(html, "html.parser")
    table = _find_non_heating_table(soup)
    customer_charge: Decimal | None = None
    components: dict[str, DeliveryComponent] = {}
    summary_amount: Decimal | None = None

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = " ".join(cells[0].get_text(" ", strip=True).split())
        value = " ".join(cells[-1].get_text(" ", strip=True).split())
        amount, unit = parse_cell(value, label)
        if "customer charge" in label.lower():
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
                f"Unsupported MA delivery unit for {label}: {value!r}"
            )
        if is_summary_row(label):
            if summary_amount is not None and summary_amount != amount:
                raise EversourceParseError(
                    "Conflicting delivery summary/total row values"
                )
            summary_amount = amount
            continue
        ee_key = _normalize_ee_key(label, selection.service_area)
        if ee_key is None and "energy efficiency" in label.lower():
            # EE line for the other service area — skip.
            continue
        key = ee_key or _stable_component_key(label)
        existing = components.get(key)
        if existing is not None and existing.rate != amount:
            raise EversourceParseError(
                f"Conflicting values for delivery component {key}"
            )
        components[key] = DeliveryComponent(key, label, amount)

    if customer_charge is None:
        raise EversourceParseError("Missing Customer Charge in MA R1 delivery")
    if not Decimal("0") < customer_charge < Decimal("200"):
        raise EversourceParseError(
            f"Customer charge outside plausible range: {customer_charge}"
        )
    missing = _REQUIRED_VARIABLE - components.keys()
    if missing:
        raise EversourceParseError(
            f"Missing required MA R1 delivery components: {sorted(missing)}"
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
