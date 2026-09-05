"""Connecticut Rate 1 parser tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.parsers import (
    EversourceParseError,
    ct as ct_parser,
    get_tariff_parser,
    parse_tariff,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ct_supply_selects_current_period() -> None:
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()
    supply = ct_parser.parse_supply_html(html, today=date(2026, 9, 5))
    assert supply.rate == Decimal("0.11577")
    assert supply.effective_date == date(2026, 7, 1)
    assert supply.expiration_date == date(2026, 12, 31)
    assert supply.rate_class == "1"


def test_parse_ct_supply_first_half_period() -> None:
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()
    supply = ct_parser.parse_supply_html(html, today=date(2026, 3, 15))
    assert supply.rate == Decimal("0.12641")
    assert supply.effective_date == date(2026, 1, 1)
    assert supply.expiration_date == date(2026, 6, 30)


def test_parse_ct_delivery_maps_groups_and_customer_charge() -> None:
    html = (FIXTURES / "sanitized_ct_delivery.html").read_text()
    delivery = ct_parser.parse_delivery_html(html)
    assert delivery.customer_charge == Decimal("9.62")
    assert set(delivery.variable_components) >= {
        "transmission_charge",
        "distribution_charge",
        "electric_system_improvements_esi_charge",
        "revenue_adjustment_mechanism",
        "competitive_transition_assessment",
        "combined_public_benefits_charge",
    }
    assert delivery.variable_rate == Decimal("0.14221")


def test_parse_tariff_dispatch_ct() -> None:
    supply, delivery = parse_tariff(
        "ct",
        "1",
        (FIXTURES / "sanitized_ct_supply.html").read_text(),
        (FIXTURES / "sanitized_ct_delivery.html").read_text(),
    )
    assert supply.rate_class == "1"
    assert delivery.customer_charge == Decimal("9.62")


def test_unsupported_ct_rate_class_has_no_parser() -> None:
    with pytest.raises(EversourceParseError, match="No tariff parser"):
        get_tariff_parser("ct", "7")


def test_ct_supply_rejects_wrong_rate_class() -> None:
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()
    with pytest.raises(EversourceParseError, match="Unsupported supply rate class"):
        ct_parser.parse_supply_html(html, rate_class="7", today=date(2026, 9, 5))


def test_ct_supply_fails_when_no_period_covers_today() -> None:
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()
    with pytest.raises(EversourceParseError, match="No CT Rate 1 supply period"):
        ct_parser.parse_supply_html(html, today=date(2027, 1, 15))


def test_ct_supply_rejects_missing_heading() -> None:
    with pytest.raises(EversourceParseError, match="Current Residential Supply"):
        ct_parser.parse_supply_html("<html><body><p>none</p></body></html>")


def test_ct_supply_rejects_missing_table() -> None:
    html = "<html><body><h2>Current Residential Supply Rates</h2></body></html>"
    with pytest.raises(EversourceParseError, match="residential supply table"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_supply_rejects_malformed_period_header() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table><tr><th>Rate</th><th>Soon</th></tr>
    <tr><td>Rate 1</td><td>12.000</td></tr></table>
    """
    with pytest.raises(EversourceParseError, match="Malformed CT supply period"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_supply_rejects_unrecognized_month() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table><tr><th>Rate</th><th>Smarch 1 - Smarch 30, 2026</th></tr>
    <tr><td>Rate 1</td><td>12.000</td></tr></table>
    """
    with pytest.raises(EversourceParseError, match="Unrecognized month"):
        ct_parser.parse_supply_html(html, today=date(2026, 3, 15))


def test_ct_supply_rejects_inverted_period() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table><tr><th>Rate</th><th>Dec 31 - Jan 1, 2026</th></tr>
    <tr><td>Rate 1</td><td>12.000</td></tr></table>
    """
    with pytest.raises(EversourceParseError, match="Inverted CT supply period"):
        ct_parser.parse_supply_html(html, today=date(2026, 1, 1))


def test_ct_supply_rejects_overlapping_periods() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table>
    <tr><th>Rate</th><th>Jan 1 - Dec 31, 2026</th><th>Jun 1 - Dec 31, 2026</th></tr>
    <tr><td>Rate 1</td><td>12.000</td><td>11.000</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Ambiguous overlapping"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_supply_rejects_duplicate_rate_1_rows() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table>
    <tr><th>Rate</th><th>Jul 1 - Dec 31, 2026</th></tr>
    <tr><td>Rate 1 / Rate 5</td><td>11.577</td></tr>
    <tr><td>Rate 1 alternate</td><td>11.000</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Conflicting CT Rate 1"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_supply_rejects_missing_rate_1_row() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table>
    <tr><th>Rate</th><th>Jul 1 - Dec 31, 2026</th></tr>
    <tr><td>Rate 7 (On-Peak)</td><td>14.129</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Could not locate Rate 1"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_supply_rejects_implausible_rate() -> None:
    html = """
    <h2>Current Residential Supply Rates</h2>
    <table>
    <tr><th>Rate</th><th>Jul 1 - Dec 31, 2026</th></tr>
    <tr><td>Rate 1</td><td>250.000</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="plausible range"):
        ct_parser.parse_supply_html(html, today=date(2026, 9, 5))


def test_ct_delivery_rejects_missing_heading() -> None:
    with pytest.raises(EversourceParseError, match="Current Rate 1 Delivery"):
        ct_parser.parse_delivery_html("<html><body><p>none</p></body></html>")


def test_ct_delivery_rejects_missing_tables() -> None:
    html = "<html><body><h2>Current Rate 1 Delivery Rates</h2></body></html>"
    with pytest.raises(EversourceParseError, match="Rate 1 delivery tables"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_missing_customer_charge() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Missing Customer Charge"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_missing_required_components() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per month)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Missing required CT Rate 1"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_conflicting_customer_charge() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per month)</td></tr>
    <tr><td>Customer Charge</td><td>$10.00 (per month)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Conflicting values for Customer"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_conflicting_component() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per month)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.06000 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Conflicting values for delivery"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_non_monthly_customer_charge() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per kWh)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="monthly dollar"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_rejects_summary_conflict() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per month)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    <tr><td>Total Delivery Rate</td><td>$0.99999 (per kWh)</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="summary/total conflicts"):
        ct_parser.parse_delivery_html(html)


def test_ct_delivery_accepts_matching_summary() -> None:
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><td>Distribution Customer Service Charge</td><td>$9.62 (per month)</td></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    <tr><td>Distribution Charge</td><td>$0.05844 (per kWh)</td></tr>
    <tr><td>Total Delivery Rate</td><td>$0.10894 (per kWh)</td></tr>
    </table>
    """
    delivery = ct_parser.parse_delivery_html(html)
    assert delivery.variable_rate == Decimal("0.10894")


def test_live_shaped_ct_delivery_without_public_benefits_table() -> None:
    """Live CT pages may omit a Public Benefits rate table under Rate 1."""
    html = """
    <h2>Current Rate 1 Delivery Rates</h2>
    <table>
    <tr><th>Transmission Component</th><th>Current Rate</th></tr>
    <tr><td>Transmission Charge</td><td>$0.05050 (per kWh)</td></tr>
    </table>
    <table>
    <tr>
      <th>Local Delivery Component</th>
      <th>Name on Your Bill</th>
      <th>Current Rate</th>
    </tr>
    <tr>
      <td>Distribution Customer Service Charge</td>
      <td>Fixed Monthly Charge</td>
      <td>$9.62 (per month)</td>
    </tr>
    <tr>
      <td>Distribution Charge</td>
      <td>Local Delivery</td>
      <td>$0.05844 (per kWh)</td>
    </tr>
    </table>
    <h2>Update Your Location</h2>
    """
    delivery = ct_parser.parse_delivery_html(html)
    assert delivery.customer_charge == Decimal("9.62")
    assert delivery.variable_rate == Decimal("0.10894")
