"""Offline parser edge-case coverage for NH Rate R HTML."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.parser import (
    EversourceParseError,
    parse_delivery_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _delivery_fixture() -> str:
    return (FIXTURES / "sanitized_delivery.html").read_text()


def test_delivery_accepts_unicode_minus_signs() -> None:
    """Normalize Unicode minus / dash signs inside numeric cells only."""
    html = (
        _delivery_fixture()
        .replace("-0.029", "\u22120.029")
        .replace("-0.148", "\u22120.148")
    )
    parsed = parse_delivery_html(html)
    assert parsed.variable_components["pole_plant_adjustment"].rate == Decimal(
        "-0.00029"
    )
    assert parsed.variable_components["stranded_cost_recovery_charge"].rate == Decimal(
        "-0.00148"
    )


def test_delivery_prefers_rate_r_table_over_earlier_lookalike() -> None:
    """Do not select an unrelated earlier table that only shares column headers."""
    decoy = (
        "<h2>Archive of Past Delivery Rates</h2>"
        "<table><thead><tr><th>Delivery Component</th>"
        "<th>Current Rate</th></tr></thead><tbody>"
        "<tr><td>Customer Charge (per month)</td><td>$1.00<br>(per month)</td></tr>"
        "<tr><td>Distribution Charge (per kWh)</td><td>1.000<br>(¢/kWh)</td></tr>"
        "</tbody></table>"
    )
    html = _delivery_fixture().replace(
        '<main class="cms">',
        f'<main class="cms">{decoy}',
    )
    parsed = parse_delivery_html(html)
    assert parsed.customer_charge == Decimal("19.81")
    assert parsed.variable_components["distribution_charge"].rate == Decimal("0.06727")


def test_delivery_accepts_zero_known_rider() -> None:
    """A present historical rider at exactly zero remains acceptable."""
    html = _delivery_fixture().replace("0.296<br>(¢/kWh)", "0.000<br>(¢/kWh)")
    parsed = parse_delivery_html(html)
    assert parsed.variable_components[
        "regulatory_reconciliation_adjustment"
    ].rate == Decimal("0")


def test_delivery_fails_closed_when_known_rider_vanishes() -> None:
    """Missing historical NH Rate R riders fail closed without stronger evidence."""
    html = _delivery_fixture().replace(
        "<tr><td>Pole Plant Adjustment Mechanism (per kWh)</td>"
        "<td>-0.029<br>(¢/kWh)</td></tr>",
        "<tr><td>Future Reliability Rider (per kWh)</td><td>0.100<br>(¢/kWh)</td></tr>",
    )
    with pytest.raises(EversourceParseError, match="Missing required"):
        parse_delivery_html(html)


def test_delivery_rejects_conflicting_duplicate_component() -> None:
    """Conflicting duplicated canonical rows must not last-write-wins."""
    html = _delivery_fixture().replace(
        "<tr><td>Distribution Charge (per kWh)</td><td>6.727<br>(¢/kWh)</td></tr>",
        "<tr><td>Distribution Charge (per kWh)</td><td>6.727<br>(¢/kWh)</td></tr>"
        "<tr><td>Distribution Charge (per kWh)</td><td>7.000<br>(¢/kWh)</td></tr>",
    )
    with pytest.raises(EversourceParseError, match="Conflicting values"):
        parse_delivery_html(html)


def test_delivery_accepts_spaced_dollar_amount_and_nbsp() -> None:
    """Tolerate common CMS spacing quirks in monthly customer charge cells."""
    html = _delivery_fixture().replace(
        "$19.81<br>(per month)", "$\u00a019.81<br>(per\u00a0month)"
    )
    parsed = parse_delivery_html(html)
    assert parsed.customer_charge == Decimal("19.81")


def test_delivery_rejects_clearly_truncated_table() -> None:
    """A Rate R-looking table missing customer charge and riders must fail."""
    html = (
        "<h2>Current Rate R Delivery Rates</h2>"
        "<table><thead><tr><th>Delivery Component</th>"
        "<th>Current Rate</th></tr></thead><tbody>"
        "<tr><td>Distribution Charge (per kWh)</td><td>6.727<br>(¢/kWh)</td></tr>"
        "</tbody></table>"
    )
    with pytest.raises(EversourceParseError):
        parse_delivery_html(html)


def test_delivery_accepts_identical_duplicate_customer_charge() -> None:
    """Identical Customer Charge rows remain acceptable."""
    html = _delivery_fixture().replace(
        "<tr><td>Customer Charge (per month)</td><td>$19.81<br>(per month)</td></tr>",
        "<tr><td>Customer Charge (per month)</td><td>$19.81<br>(per month)</td></tr>"
        "<tr><td>Customer Charge (per month)</td><td>$19.81<br>(per month)</td></tr>",
    )
    parsed = parse_delivery_html(html)
    assert parsed.customer_charge == Decimal("19.81")


def test_delivery_rejects_conflicting_duplicate_customer_charge() -> None:
    """Conflicting Customer Charge amounts fail closed like variable duplicates."""
    html = _delivery_fixture().replace(
        "<tr><td>Customer Charge (per month)</td><td>$19.81<br>(per month)</td></tr>",
        "<tr><td>Customer Charge (per month)</td><td>$19.81<br>(per month)</td></tr>"
        "<tr><td>Customer Charge (per month)</td><td>$20.00<br>(per month)</td></tr>",
    )
    with pytest.raises(EversourceParseError, match="Conflicting values for Customer"):
        parse_delivery_html(html)
