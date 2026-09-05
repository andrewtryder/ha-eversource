"""Test suite for Eversource Rate R parser and calculations."""

from decimal import Decimal
from pathlib import Path

import pytest

from tools.fetch_eversource_rates import (
    TariffParseError,
    TariffRates,
    parse_delivery_html,
    parse_supply_html,
    validate_rates,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def supply_html() -> str:
    fixture_path = FIXTURES_DIR / "sanitized_supply.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def delivery_html() -> str:
    fixture_path = FIXTURES_DIR / "sanitized_delivery.html"
    return fixture_path.read_text(encoding="utf-8")


def test_parse_supply_html(supply_html: str):
    """Verify supply rate extraction and effective period from sanitized fixture."""
    rate, start_date, end_date = parse_supply_html(supply_html)
    assert rate == Decimal("0.14009")
    assert start_date == "August 1, 2026"
    assert end_date == "January 31, 2027"


def test_parse_delivery_html(delivery_html: str):
    """Verify components, fixed charge, and variable delivery-rate summation."""
    customer_charge, delivery_rate, components = parse_delivery_html(delivery_html)

    # Verify customer charge (fixed monthly)
    assert customer_charge == Decimal("19.81")

    # Verify individual components normalized to USD/kWh
    assert components["distribution_charge"] == Decimal("0.06727")
    assert components["regulatory_reconciliation_adjustment"] == Decimal("0.00296")
    assert components["pole_plant_adjustment"] == Decimal("-0.00029")
    assert components["transmission_charge"] == Decimal("0.04445")
    assert components["stranded_cost_recovery_charge"] == Decimal("-0.00148")
    assert components["system_benefits_charge"] == Decimal("0.00618")

    # Verify exact summation of delivery components:
    # 0.06727 + 0.00296 - 0.00029 + 0.04445 - 0.00148 + 0.00618 = 0.11909
    expected_delivery = (
        Decimal("0.06727")
        + Decimal("0.00296")
        - Decimal("0.00029")
        + Decimal("0.04445")
        - Decimal("0.00148")
        + Decimal("0.00618")
    )
    assert delivery_rate == Decimal("0.11909")
    assert delivery_rate == expected_delivery


def test_total_variable_rate(supply_html: str, delivery_html: str):
    """Verify total variable rate (supply + delivery) calculation."""
    supply_rate, _, _ = parse_supply_html(supply_html)
    customer_charge, delivery_rate, components = parse_delivery_html(delivery_html)

    total_variable_rate = supply_rate + delivery_rate
    expected_total = Decimal("0.14009") + Decimal("0.11909")

    assert total_variable_rate == Decimal("0.25918")
    assert total_variable_rate == expected_total

    rates = TariffRates(
        supply_rate=supply_rate,
        delivery_rate=delivery_rate,
        total_variable_rate=total_variable_rate,
        monthly_customer_charge=customer_charge,
        delivery_components=components,
        supply_effective_start="August 1, 2026",
        supply_effective_end="January 31, 2027",
        retrieval_timestamp="2026-09-05T00:00:00Z",
        supply_source_url="https://example.com/supply",
        delivery_source_url="https://example.com/delivery",
    )
    # Should pass validation without error
    validate_rates(rates)


def test_negative_adjustments_supported():
    """Verify parser explicitly handles negative numbers in table cells."""
    sample_table_html = """
    <table>
      <thead><tr><th>Delivery Component</th><th>Current Rate</th></tr></thead>
      <tr><td>Customer Charge (per month)</td><td>$19.81</td></tr>
      <tr><td>Distribution Charge (per kWh)</td><td>6.727 (¢/kWh)</td></tr>
      <tr><td>Regulatory Reconciliation Adjustment (per kWh)</td>
          <td>0.296 (¢/kWh)</td></tr>
      <tr><td>Pole Plant Adjustment Mechanism (per kWh)</td><td>-0.029 (¢/kWh)</td></tr>
      <tr><td>Transmission Charge</td><td>4.445 (¢/kWh)</td></tr>
      <tr><td>Stranded Cost Recovery Charge (per kWh)</td><td>-0.148 (¢/kWh)</td></tr>
      <tr><td>System Benefits Charge (per kWh)</td><td>0.618 (¢/kWh)</td></tr>
    </table>
    """
    customer_charge, delivery_rate, components = parse_delivery_html(sample_table_html)
    assert components["pole_plant_adjustment"] < Decimal("0")
    assert components["stranded_cost_recovery_charge"] < Decimal("0")
    assert delivery_rate == Decimal("0.11909")


def test_missing_supply_rate_raises():
    """Verify error raised when supply rate label is missing."""
    empty_html = "<html><body><p>No rates here.</p></body></html>"
    with pytest.raises(TariffParseError, match="Could not locate Rate R supply rate"):
        parse_supply_html(empty_html)


def test_missing_delivery_table_raises():
    """Verify error raised when delivery table is missing."""
    empty_html = "<html><body><p>No delivery table.</p></body></html>"
    with pytest.raises(
        TariffParseError, match="Could not locate Rate R delivery table"
    ):
        parse_delivery_html(empty_html)


def test_missing_component_raises():
    """Verify error raised when a required component is missing from delivery table."""
    incomplete_table_html = """
    <table>
      <thead><tr><th>Delivery Component</th><th>Current Rate</th></tr></thead>
      <tr><td>Customer Charge (per month)</td><td>$19.81</td></tr>
      <tr><td>Distribution Charge (per kWh)</td><td>6.727 (¢/kWh)</td></tr>
    </table>
    """
    with pytest.raises(TariffParseError, match="Missing required delivery components"):
        parse_delivery_html(incomplete_table_html)


def test_validate_rates_out_of_range():
    """Verify validator flags unreasonable tariff numbers."""
    bad_rates = TariffRates(
        supply_rate=Decimal("1.50"),  # Implausibly high
        delivery_rate=Decimal("0.11909"),
        total_variable_rate=Decimal("1.61909"),
        monthly_customer_charge=Decimal("19.81"),
        delivery_components={},
        supply_effective_start=None,
        supply_effective_end=None,
        retrieval_timestamp="",
        supply_source_url="",
        delivery_source_url="",
    )
    with pytest.raises(TariffParseError, match="outside plausible range"):
        validate_rates(bad_rates)
