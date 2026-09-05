"""Behavior tests for the developer tariff-fetch utility."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.fetch_eversource_rates import _display_date, fetch_eversource_rates


@pytest.mark.asyncio
async def test_fetch_utility_constructs_keyword_only_client(rates) -> None:
    """Prove the tool uses the current EversourceClient keyword API."""
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "tools.fetch_eversource_rates.aiohttp.ClientSession",
            return_value=session_cm,
        ),
        patch("tools.fetch_eversource_rates.EversourceClient") as client_cls,
    ):
        client_cls.return_value.async_get_rates = AsyncMock(return_value=rates)
        result = await fetch_eversource_rates()

    assert client_cls.call_args.args == (session,)
    assert client_cls.call_args.kwargs == {
        "territory": "nh",
        "rate_class": "r",
    }
    assert result.supply_rate == rates.supply.rate
    assert result.total_variable_rate == rates.total_variable_rate
    assert result.supply_effective_start == "August 1, 2026"
    assert result.supply_effective_end == "January 31, 2027"


def test_display_date_is_platform_independent() -> None:
    """Avoid strftime %-d so Windows and POSIX format the same way."""
    assert _display_date(date(2026, 9, 5)) == "September 5, 2026"
    assert _display_date(None) is None
