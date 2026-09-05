"""Western Massachusetts R1 parser and dispatch tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.parsers import (
    EversourceParseError,
    ma as ma_parser,
    parse_tariff,
)
from custom_components.eversource_rates.tariffs import TariffSelection

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_wma_fixed_supply_current_period() -> None:
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    selection = TariffSelection("wma", "r1", supply_plan="fixed")
    supply = ma_parser.parse_supply_html(html, selection, today=date(2026, 9, 5))
    assert supply.rate == Decimal("0.15934")
    assert supply.effective_date == date(2026, 8, 1)
    assert supply.expiration_date == date(2027, 1, 31)


def test_parse_wma_monthly_variable_supply_current_month() -> None:
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    selection = TariffSelection("wma", "r1", supply_plan="monthly_variable")
    supply = ma_parser.parse_supply_html(html, selection, today=date(2026, 9, 5))
    assert supply.rate == Decimal("0.11620")
    assert supply.effective_date == date(2026, 9, 1)
    assert supply.expiration_date == date(2026, 9, 30)


def test_parse_wma_delivery_non_heating_only() -> None:
    html = (FIXTURES / "sanitized_wma_delivery.html").read_text()
    selection = TariffSelection("wma", "r1", supply_plan="fixed")
    delivery = ma_parser.parse_delivery_html(html, selection)
    assert delivery.customer_charge == Decimal("10.00")
    assert delivery.variable_components["transition_energy_charge"].rate == Decimal(
        "-0.00077"
    )
    assert "energy_efficiency_charge" in delivery.variable_components
    # Heat-pump seasonal rows must not leak into R1 Non-Heating.
    assert "distribution_energy_charge_winter_november_april" not in (
        delivery.variable_components
    )
    assert delivery.variable_rate == Decimal("0.18635")


def test_parse_tariff_dispatch_wma() -> None:
    selection = TariffSelection("wma", "r1", supply_plan="fixed")
    supply, delivery = parse_tariff(
        selection,
        (FIXTURES / "sanitized_wma_supply.html").read_text(),
        (FIXTURES / "sanitized_wma_delivery.html").read_text(),
    )
    assert supply.rate == Decimal("0.15934")
    assert delivery.customer_charge == Decimal("10.00")


def test_unsupported_wma_rate_class_has_no_parser() -> None:
    with pytest.raises(EversourceParseError, match="No tariff parser"):
        parse_tariff(
            TariffSelection("wma", "r2", supply_plan="fixed"),
            "<html></html>",
            "<html></html>",
        )


def test_wma_supply_rejects_missing_plan() -> None:
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    with pytest.raises(EversourceParseError, match="Unsupported MA supply plan"):
        ma_parser.parse_supply_html(
            html, TariffSelection("wma", "r1"), today=date(2026, 9, 5)
        )


def test_wma_fixed_rejects_uncovered_date() -> None:
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    with pytest.raises(EversourceParseError, match="No MA Fixed Basic Service period"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="fixed"),
            today=date(2027, 6, 1),
        )


def test_wma_monthly_rejects_uncovered_date() -> None:
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    with pytest.raises(EversourceParseError, match="No MA Monthly Variable period"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="monthly_variable"),
            today=date(2026, 2, 1),
        )


def test_wma_delivery_rejects_missing_section() -> None:
    with pytest.raises(EversourceParseError, match="Non-Heating"):
        ma_parser.parse_delivery_html(
            "<html><body><p>none</p></body></html>",
            TariffSelection("wma", "r1", supply_plan="fixed"),
        )


def test_wma_delivery_rejects_missing_customer_charge() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Missing Customer Charge"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ema_delivery_selects_service_area_ee_charge() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr>
      <td>Energy Efficiency Charge (Greater Boston, Cambridge and South Shore only)</td>
      <td>$0.02292 per kWh</td>
    </tr>
    <tr>
      <td>Energy Efficiency Charge (Cape Cod and Martha's Vineyard only)</td>
      <td>$0.03738 per kWh</td>
    </tr>
    </table>
    """
    main = ma_parser.parse_delivery_html(
        html, TariffSelection("ema", "r1", supply_plan="fixed", service_area="main")
    )
    cape = ma_parser.parse_delivery_html(
        html, TariffSelection("ema", "r1", supply_plan="fixed", service_area="cape")
    )
    assert main.variable_components["energy_efficiency_charge"].rate == Decimal(
        "0.02292"
    )
    assert cape.variable_components["energy_efficiency_charge"].rate == Decimal(
        "0.03738"
    )


def test_ma_supply_rejects_wrong_rate_class() -> None:
    with pytest.raises(EversourceParseError, match="Unsupported MA supply rate class"):
        ma_parser.parse_supply_html(
            (FIXTURES / "sanitized_wma_supply.html").read_text(),
            TariffSelection("wma", "r2", supply_plan="fixed"),
            today=date(2026, 9, 5),
        )


def test_ma_delivery_rejects_wrong_rate_class() -> None:
    with pytest.raises(EversourceParseError, match="Unsupported MA delivery"):
        ma_parser.parse_delivery_html(
            (FIXTURES / "sanitized_wma_delivery.html").read_text(),
            TariffSelection("wma", "r2", supply_plan="fixed"),
        )


def test_ma_delivery_rejects_missing_required_components() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Missing required MA R1"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_delivery_rejects_non_monthly_customer_charge() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per kWh</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="monthly dollar"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_delivery_rejects_conflicting_components() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09900 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Conflicting values"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_delivery_rejects_summary_conflict() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    <tr><td>Total Delivery Rate</td><td>$0.99999 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="summary/total conflicts"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_delivery_rejects_implausible_customer_charge() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$250.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Customer charge outside"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_decimal_rejects_malformed_amount() -> None:
    from custom_components.eversource_rates.parsers.common import (
        EversourceParseError,
        decimal,
    )

    with pytest.raises(EversourceParseError, match="Malformed"):
        decimal("not-a-number", "test")


def test_ma_delivery_rejects_implausible_variable_rate() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.50000 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.50000 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.50000 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Delivery rate outside"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_fixed_rejects_inverted_period() -> None:
    html = """
    <h4>Fixed Rate</h4>
    <ul><li>December 31, 2026 through January 1, 2026 - $0.15000</li></ul>
    """
    with pytest.raises(EversourceParseError, match="Inverted MA Fixed"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="fixed"),
            today=date(2026, 1, 1),
        )


def test_ma_fixed_rejects_missing_periods() -> None:
    html = "<h4>Fixed Rate</h4><p>No rates listed.</p>"
    with pytest.raises(EversourceParseError, match="Could not locate MA Fixed"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="fixed"),
            today=date(2026, 9, 5),
        )


def test_ma_monthly_rejects_missing_periods() -> None:
    html = "<h4>Monthly Variable Rate</h4><p>No rates listed.</p>"
    with pytest.raises(EversourceParseError, match="Could not locate MA Monthly"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="monthly_variable"),
            today=date(2026, 9, 5),
        )


def test_ma_delivery_rejects_conflicting_customer_charge() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Customer Charge</td><td>$11.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per kWh</td></tr>
    <tr><td>Transmission Charge</td><td>$0.04673 per kWh</td></tr>
    <tr><td>Energy Efficiency Charge</td><td>$0.02292 per kWh</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Conflicting values for Customer"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_delivery_rejects_unsupported_variable_unit() -> None:
    html = """
    <h3>Residential, Non-Heating</h3>
    <table>
    <tr><td>Customer Charge</td><td>$10.00 per month</td></tr>
    <tr><td>Distribution Energy Charge</td><td>$0.09837 per day</td></tr>
    </table>
    """
    with pytest.raises(EversourceParseError, match="Unsupported or malformed unit"):
        ma_parser.parse_delivery_html(
            html, TariffSelection("wma", "r1", supply_plan="fixed")
        )


def test_ma_unrecognized_month_fails() -> None:
    html = """
    <h4>Fixed Rate</h4>
    <ul><li>Smarch 1, 2026 through Smarch 31, 2026 - $0.15000</li></ul>
    """
    with pytest.raises(EversourceParseError, match="Unrecognized month"):
        ma_parser.parse_supply_html(
            html,
            TariffSelection("wma", "r1", supply_plan="fixed"),
            today=date(2026, 3, 15),
        )
