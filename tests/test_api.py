"""Offline HTTP client behavior tests."""

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from custom_components.eversource_rates.api import (
    EversourceClient,
    EversourceConnectionError,
    EversourceTariffParseError,
    EversourceUnsupportedTariffError,
)
from custom_components.eversource_rates.const import DELIVERY_URL, SUPPLY_URL
from custom_components.eversource_rates.sources import TARIFF_SOURCES, TariffSource

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(
        self, status: int, text: str, url: str = "https://example.test"
    ) -> None:
        self.status, self._text, self.url = status, text, url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def text(self) -> str:
        return self._text


class FakeSession:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class TimeoutSession:
    def get(self, *_args, **_kwargs):
        raise TimeoutError


def _client(session, *, territory="nh", rate_class="r") -> EversourceClient:
    return EversourceClient(
        session,
        territory=territory,
        rate_class=rate_class,
    )


def test_dual_fetch_uses_only_explicit_segment_cookie() -> None:
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(_client(session).async_get_rates())
    assert str(rates.total_variable_rate) == "0.25918"
    assert rates.territory == "nh"
    assert rates.source_supply_url == SUPPLY_URL
    assert rates.source_delivery_url == DELIVERY_URL
    assert all(
        call[1]["headers"] == {"Cookie": ".SEGMENT=nh"} for call in session.calls
    )


def test_ct_fetch_uses_suffixed_urls_without_cookie() -> None:
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_ct_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_ct_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(
        _client(session, territory="ct", rate_class="1").async_get_rates()
    )
    assert rates.territory == "ct"
    assert rates.rate_class == "1"
    assert rates.source_supply_url == f"{SUPPLY_URL}/ct"
    assert rates.source_delivery_url == f"{DELIVERY_URL}/ct"
    assert [call[0] for call in session.calls] == [
        f"{SUPPLY_URL}/ct",
        f"{DELIVERY_URL}/ct",
    ]
    assert all(call[1]["headers"] == {} for call in session.calls)


def test_nh_fetch_cookie_comes_from_tariff_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP cookie comes from TariffSource, not a hard-coded territory string."""
    monkeypatch.setitem(
        TARIFF_SOURCES,
        ("nh", "r"),
        TariffSource(SUPPLY_URL, DELIVERY_URL, segment="completely-different-segment"),
    )
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(_client(session).async_get_rates())
    assert rates.territory == "nh"
    assert all(
        call[1]["headers"] == {"Cookie": ".SEGMENT=completely-different-segment"}
        for call in session.calls
    )


def test_support_dispatch_uses_logical_territory_not_cookie_value() -> None:
    """Unsupported logical territories fail even if a CT-looking cookie would exist."""
    with pytest.raises(EversourceUnsupportedTariffError):
        asyncio.run(
            _client(FakeSession([]), territory="ct", rate_class="r").async_get_rates()
        )
    with pytest.raises(EversourceUnsupportedTariffError):
        asyncio.run(
            _client(FakeSession([]), territory="ct", rate_class="7").async_get_rates()
        )


@pytest.mark.parametrize("status", [403, 404, 500])
def test_http_errors_fail_safely(status: int) -> None:
    with pytest.raises(EversourceConnectionError):
        asyncio.run(
            _client(FakeSession([FakeResponse(status, "no")])).async_get_rates()
        )


def test_timeout_fails_safely() -> None:
    with pytest.raises(EversourceConnectionError, match="Timed out"):
        asyncio.run(_client(TimeoutSession()).async_get_rates())


def test_unsupported_tariff_fails_before_network_access() -> None:
    """Reject a non-production tariff without attempting an HTTP request."""
    with pytest.raises(EversourceUnsupportedTariffError):
        asyncio.run(
            _client(FakeSession([]), territory="ema", rate_class="r1").async_get_rates()
        )


def test_malformed_supply_fails_safely() -> None:
    session = FakeSession(
        [
            FakeResponse(200, "<p>none</p>"),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    with pytest.raises(EversourceTariffParseError):
        asyncio.run(_client(session).async_get_rates())


def test_aiohttp_client_error_fails_safely() -> None:
    class BrokenSession:
        def get(self, *_args, **_kwargs):
            import aiohttp

            raise aiohttp.ClientError("boom")

    with pytest.raises(EversourceConnectionError, match="Unable to retrieve"):
        asyncio.run(_client(BrokenSession()).async_get_rates())


def test_implausible_total_variable_rate_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.eversource_rates import api as api_mod
    from custom_components.eversource_rates.models import (
        DeliveryComponent,
        DeliveryRates,
        SupplyRate,
    )

    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )

    def _implausible(*_args, **_kwargs):
        return (
            SupplyRate(Decimal("1.5"), None, None, "r"),
            DeliveryRates(
                Decimal("19.81"),
                {
                    "distribution_charge": DeliveryComponent(
                        "distribution_charge", "Distribution", Decimal("0.6")
                    )
                },
            ),
        )

    monkeypatch.setattr(api_mod, "parse_tariff", _implausible)
    with pytest.raises(EversourceTariffParseError, match="plausible range"):
        asyncio.run(_client(session).async_get_rates())
