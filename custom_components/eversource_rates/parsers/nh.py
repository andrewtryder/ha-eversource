"""New Hampshire Residential Rate R public tariff parsers."""

from __future__ import annotations

import re
from datetime import date, datetime
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

_SUPPLY_PATTERN = re.compile(
    r"Rate\s+R\s+will\s+be\s+\$([0-9]+(?:\.[0-9]+)?)\s+per\s+kWh"
    r"(?:\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+through\s+"
    r"([A-Za-z]+\s+\d{1,2},\s+\d{4}))?",
    re.IGNORECASE,
)
_KNOWN_COMPONENTS = {
    "distribution charge": "distribution_charge",
    "regulatory reconciliation": "regulatory_reconciliation_adjustment",
    "pole plant adjustment": "pole_plant_adjustment",
    "transmission charge": "transmission_charge",
    "stranded cost recovery": "stranded_cost_recovery_charge",
    "system benefits": "system_benefits_charge",
}
_REQUIRED_COMPONENTS = frozenset(_KNOWN_COMPONENTS.values())


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%B %d, %Y").date()
    except ValueError as err:
        raise EversourceParseError(f"Malformed supply date: {value!r}") from err


def _nh_component_key(label: str) -> str:
    normalized = " ".join(label.lower().split())
    for phrase, key in _KNOWN_COMPONENTS.items():
        if phrase in normalized:
            return key
    return component_key(label)


def parse_supply_html(html: str, rate_class: str = "r") -> SupplyRate:
    """Extract NH Rate R supply beneath the semantic Current Supply Rates heading."""
    if rate_class != "r":
        # This parser only recognizes Rate R supply sentences; refuse mislabeling.
        raise EversourceParseError(
            f"Unsupported supply rate class for NH Rate R parser: {rate_class!r}"
        )
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (
            h
            for h in soup.find_all(["h1", "h2", "h3"])
            if "current supply rates" in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is None:
        raise EversourceParseError(
            "Could not locate Rate R supply rate (Current Supply Rates section missing)"
        )
    container: Tag = heading.parent if isinstance(heading.parent, Tag) else soup
    match = _SUPPLY_PATTERN.search(container.get_text(" ", strip=True))
    if match is None:
        raise EversourceParseError("Could not locate Rate R supply rate")
    rate = decimal(match.group(1), "supply rate")
    if not Decimal("0") < rate < Decimal("1"):
        raise EversourceParseError(f"Supply rate outside plausible range: {rate}")
    return SupplyRate(
        rate, _parse_date(match.group(2)), _parse_date(match.group(3)), rate_class
    )


def _is_delivery_candidate(table: Tag) -> bool:
    headers = {
        " ".join(th.get_text(" ", strip=True).lower().split())
        for th in table.find_all("th")
    }
    return {"delivery component", "current rate"}.issubset(headers)


def _find_rate_r_delivery_table(soup: BeautifulSoup) -> Tag:
    """Locate the Rate R delivery table by heading proximity, not table ordinal."""
    heading = next(
        (
            h
            for h in soup.find_all(["h1", "h2", "h3"])
            if "current rate r delivery" in h.get_text(" ", strip=True).lower()
        ),
        None,
    )
    if heading is not None:
        for table in heading.find_all_next("table"):
            if _is_delivery_candidate(table):
                return table
        raise EversourceParseError(
            "Could not locate Rate R delivery table near Current Rate R Delivery Rates"
        )

    candidates = [
        table for table in soup.find_all("table") if _is_delivery_candidate(table)
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise EversourceParseError("Could not locate Rate R delivery table")


def parse_delivery_html(html: str) -> DeliveryRates:  # noqa: C901
    """Extract the Rate R table by headers and classify every per-kWh row."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_rate_r_delivery_table(soup)
    customer_charge: Decimal | None = None
    components: dict[str, DeliveryComponent] = {}
    summary_amount: Decimal | None = None
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label, value = (cell.get_text(" ", strip=True) for cell in cells[:2])
        amount, unit = parse_cell(value, label)
        if "customer charge" in label.lower():
            if unit != "USD/month":
                raise EversourceParseError(
                    "Customer charge is not a monthly dollar value"
                )
            if customer_charge is not None and customer_charge != amount:
                raise EversourceParseError("Conflicting values for Customer Charge")
            customer_charge = amount
        elif unit == "USD/kWh":
            if is_summary_row(label):
                if summary_amount is not None and summary_amount != amount:
                    raise EversourceParseError(
                        "Conflicting delivery summary/total row values"
                    )
                summary_amount = amount
                continue
            key = _nh_component_key(label)
            existing = components.get(key)
            if existing is not None and existing.rate != amount:
                raise EversourceParseError(
                    f"Conflicting values for delivery component {key}"
                )
            components[key] = DeliveryComponent(key, label, amount)
    if customer_charge is None:
        raise EversourceParseError("Missing Customer Charge in delivery table")
    if not Decimal("0") < customer_charge < Decimal("200"):
        raise EversourceParseError(
            f"Customer charge outside plausible range: {customer_charge}"
        )
    missing = _REQUIRED_COMPONENTS - components.keys()
    if missing:
        # Fail closed: without evidence that NH Rate R riders can disappear
        # legitimately, a missing historical component is treated as truncated.
        raise EversourceParseError(
            f"Missing required delivery components: {sorted(missing)}"
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
