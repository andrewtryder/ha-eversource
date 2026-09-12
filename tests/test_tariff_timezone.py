"""Regression tests for Eastern Time tariff date evaluation.

Ensures that tariff effective periods are evaluated against the service
territory's local time (America/New_York) rather than the local system clock
of the host running Home Assistant (e.g. UTC).
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from custom_components.eversource_rates.api import EversourceClient
from custom_components.eversource_rates.const import (
    EVERSOURCE_TIME_ZONE,
    TERRITORIES,
)
from custom_components.eversource_rates.parsers import ct, ma
from custom_components.eversource_rates.sources import TARIFF_SOURCES
from custom_components.eversource_rates.tariffs import TariffSelection

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text
        self.status = 200

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def text(self) -> str:
        return self._text


class _FakeSession:
    def __init__(self, supply_html: str, delivery_html: str) -> None:
        self.supply_html = supply_html
        self.delivery_html = delivery_html

    def get(self, url: str, **kwargs) -> _FakeResponse:
        text = self.supply_html if "supply" in url else self.delivery_html
        return _FakeResponse(text)


def test_territories_and_sources_use_eastern_time() -> None:
    """Verify all territories and tariff sources configure Eastern Time."""
    assert EVERSOURCE_TIME_ZONE == ZoneInfo("America/New_York")
    for territory in TERRITORIES.values():
        assert territory.time_zone == EVERSOURCE_TIME_ZONE
    for source in TARIFF_SOURCES.values():
        assert source.time_zone == EVERSOURCE_TIME_ZONE


def test_ct_supply_period_end_boundary(freezer) -> None:
    """At 23:59:59 ET on period end, CT parser selects the ending period."""
    # 2026-06-30 23:59:59 EDT == 2026-07-01 03:59:59 UTC
    freezer.move_to("2026-07-01 03:59:59+00:00")
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()

    # Without explicit today, defaults to current time in America/New_York
    supply = ct.parse_supply_html(html)
    assert supply.rate == Decimal("0.12641")
    assert supply.effective_date == date(2026, 1, 1)
    assert supply.expiration_date == date(2026, 6, 30)


def test_ct_supply_next_period_boundary(freezer) -> None:
    """At 00:00:01 ET on period start, CT parser selects the new period."""
    # 2026-07-01 00:00:01 EDT == 2026-07-01 04:00:01 UTC
    freezer.move_to("2026-07-01 04:00:01+00:00")
    html = (FIXTURES / "sanitized_ct_supply.html").read_text()

    supply = ct.parse_supply_html(html)
    assert supply.rate == Decimal("0.11577")
    assert supply.effective_date == date(2026, 7, 1)
    assert supply.expiration_date == date(2026, 12, 31)


def test_ma_monthly_variable_month_end_boundary_on_utc_host(freezer) -> None:
    """A UTC host on 1st of next month evaluates to prior month if still prior in ET."""
    # 2026-08-31 23:59:30 EDT is 2026-09-01 03:59:30 UTC.
    # UTC rolled to Sep 1, but in Massachusetts it is still Aug 31.
    freezer.move_to("2026-09-01 03:59:30+00:00")
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    selection = TariffSelection("wma", "r1", supply_plan="monthly_variable")

    supply = ma.parse_supply_html(html, selection)
    assert supply.rate == Decimal("0.13191")  # August 2026 rate
    assert supply.effective_date == date(2026, 8, 1)
    assert supply.expiration_date == date(2026, 8, 31)


def test_ma_monthly_variable_new_month_boundary(freezer) -> None:
    """At 00:00:05 ET on the 1st of month, MA monthly variable rolls to new month."""
    # 2026-09-01 00:00:05 EDT == 2026-09-01 04:00:05 UTC
    freezer.move_to("2026-09-01 04:00:05+00:00")
    html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    selection = TariffSelection("wma", "r1", supply_plan="monthly_variable")

    supply = ma.parse_supply_html(html, selection)
    assert supply.rate == Decimal("0.11620")  # September 2026 rate
    assert supply.effective_date == date(2026, 9, 1)
    assert supply.expiration_date == date(2026, 9, 30)


def test_api_client_evaluates_eastern_time_on_utc_host(freezer) -> None:
    """EversourceClient passes ET as_of to parser even when UTC host rolled over."""
    # 2026-08-31 22:30:00 EDT == 2026-09-01 02:30:00 UTC
    freezer.move_to("2026-09-01 02:30:00+00:00")
    supply_html = (FIXTURES / "sanitized_wma_supply.html").read_text()
    delivery_html = (FIXTURES / "sanitized_wma_delivery.html").read_text()

    session = _FakeSession(supply_html, delivery_html)
    client = EversourceClient(
        session,  # type: ignore[arg-type]
        selection=TariffSelection("wma", "r1", supply_plan="monthly_variable"),
    )
    rates = asyncio.run(client.async_get_rates())
    assert rates.supply.rate == Decimal("0.13191")  # August rate, not September
    assert rates.supply.effective_date == date(2026, 8, 1)
