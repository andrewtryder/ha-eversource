"""Additional offline coverage for production parser behavior."""

from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.parser import (
    EversourceParseError,
    parse_delivery_html,
    parse_supply_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_supply_ignores_unrelated_money_and_whitespace() -> None:
    html = (
        "<h2>Current Supply Rates</h2><p>Rate R will be $0.14009 per kWh "
        "August 1, 2026 through January 31, 2027.</p><p>$99/kWh elsewhere</p>"
    )
    parsed = parse_supply_html(html)
    assert parsed.rate == Decimal("0.14009")
    assert parsed.effective_date.isoformat() == "2026-08-01"


def test_delivery_accepts_reordered_rows_and_unknown_rider() -> None:
    html = (
        (FIXTURES / "sanitized_delivery.html")
        .read_text()
        .replace(
            "<tr><td>Distribution Charge",
            "<tr><td>Future Reliability Rider (per kWh)</td>"
            "<td>0.100<br>(¢/kWh)</td></tr><tr><td>Distribution Charge",
        )
    )
    parsed = parse_delivery_html(html)
    assert parsed.variable_components[
        "future_reliability_rider_per_kwh"
    ].rate == Decimal("0.001")
    assert parsed.variable_rate == Decimal("0.12009")


def test_delivery_rejects_missing_headers() -> None:
    html = (
        (FIXTURES / "sanitized_delivery.html")
        .read_text()
        .replace(
            "<th>Delivery Component</th><th>Current Rate</th>",
            "<th>Thing</th><th>Amount</th>",
        )
    )
    with pytest.raises(EversourceParseError, match="delivery table"):
        parse_delivery_html(html)


def test_delivery_rejects_malformed_units() -> None:
    html = (
        (FIXTURES / "sanitized_delivery.html")
        .read_text()
        .replace("6.727<br>(¢/kWh)", "6.727 bananas")
    )
    with pytest.raises(EversourceParseError, match="unit"):
        parse_delivery_html(html)


def test_supply_rejects_implausible_rate() -> None:
    html = "<h2>Current Supply Rates</h2><p>Rate R will be $19.81 per kWh</p>"
    with pytest.raises(EversourceParseError, match="plausible"):
        parse_supply_html(html)


def test_supply_rejects_malformed_effective_date() -> None:
    """Reject a recognized supply sentence with an impossible effective date."""
    html = (
        "<h2>Current Supply Rates</h2><p>Rate R will be $0.14009 per kWh "
        "February 31, 2026 through January 31, 2027.</p>"
    )
    with pytest.raises(EversourceParseError, match="Malformed supply date"):
        parse_supply_html(html)


def test_supply_rate_class_r_still_parses() -> None:
    """Explicit Rate R remains the only successful supply parse path."""
    html = (
        "<h2>Current Supply Rates</h2><p>Rate R will be $0.14009 per kWh "
        "August 1, 2026 through January 31, 2027.</p>"
    )
    parsed = parse_supply_html(html, rate_class="r")
    assert parsed.rate_class == "r"
    assert parsed.rate == Decimal("0.14009")


def test_supply_rejects_unsupported_rate_class_label() -> None:
    """Refuse to return Rate R numbers labeled as an unsupported rate class."""
    html = (
        "<h2>Current Supply Rates</h2><p>Rate R will be $0.14009 per kWh "
        "August 1, 2026 through January 31, 2027.</p>"
    )
    with pytest.raises(EversourceParseError, match="Unsupported supply rate class"):
        parse_supply_html(html, rate_class="g")
