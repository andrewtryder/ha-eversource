"""Delivery summary/total row classification and fail-closed checks."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.parser import (
    EversourceParseError,
    _is_summary_row,
    parse_delivery_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _delivery_fixture() -> str:
    return (FIXTURES / "sanitized_delivery.html").read_text()


@pytest.mark.parametrize(
    "label",
    [
        "Total",
        "Subtotal",
        "Total Delivery Rate",
        "Total Delivery Charge",
        "Total Variable Rate",
        "Delivery Total",
        "Total Delivery Rate (per kWh)",
    ],
)
def test_is_summary_row_recognizes_totals(label: str) -> None:
    """Recognized total/subtotal labels are non-additive."""
    assert _is_summary_row(label) is True


@pytest.mark.parametrize(
    "label",
    [
        "Distribution Charge (per kWh)",
        "System Benefits Charge (per kWh)",
        "Total System Benefits Charge",
        "Hospital Total Adjustment",
    ],
)
def test_is_summary_row_does_not_overmatch_riders(label: str) -> None:
    """Rider labels that merely contain 'total' remain additive components."""
    assert _is_summary_row(label) is False


def test_matching_total_delivery_row_is_not_double_counted() -> None:
    """A consistent Total Delivery Rate is validated and excluded from the sum."""
    html = _delivery_fixture().replace(
        "</tbody>",
        "<tr><td>Total Delivery Rate</td><td>11.909<br>(¢/kWh)</td></tr></tbody>",
    )
    parsed = parse_delivery_html(html)
    assert parsed.variable_rate == Decimal("0.11909")
    assert "total_delivery_rate" not in parsed.variable_components
    assert len(parsed.variable_components) == 6


def test_conflicting_total_delivery_row_fails_closed() -> None:
    """A summary that disagrees with the component sum is rejected."""
    html = _delivery_fixture().replace(
        "</tbody>",
        "<tr><td>Total Delivery Rate</td><td>99.000<br>(¢/kWh)</td></tr></tbody>",
    )
    with pytest.raises(EversourceParseError, match="conflicts with component sum"):
        parse_delivery_html(html)


def test_ordinary_unknown_rider_still_included() -> None:
    """Unknown legitimate /kWh riders remain additive components."""
    html = _delivery_fixture().replace(
        "</tbody>",
        "<tr><td>Future Reliability Rider (per kWh)</td>"
        "<td>0.100<br>(¢/kWh)</td></tr></tbody>",
    )
    parsed = parse_delivery_html(html)
    assert parsed.variable_components[
        "future_reliability_rider_per_kwh"
    ].rate == Decimal("0.001")
    assert parsed.variable_rate == Decimal("0.12009")


def test_historical_required_riders_unchanged_with_matching_total() -> None:
    """Required NH Rate R riders remain present when a matching total is added."""
    html = _delivery_fixture().replace(
        "</tbody>",
        "<tr><td>Total Variable Delivery Rate</td>"
        "<td>11.909<br>(¢/kWh)</td></tr></tbody>",
    )
    parsed = parse_delivery_html(html)
    assert set(parsed.variable_components) >= {
        "distribution_charge",
        "regulatory_reconciliation_adjustment",
        "pole_plant_adjustment",
        "transmission_charge",
        "stranded_cost_recovery_charge",
        "system_benefits_charge",
    }
