"""Offline HTTP client behavior tests."""

import asyncio
from pathlib import Path

import pytest

from custom_components.eversource_rates.api import (
    EversourceClient,
    EversourceConnectionError,
    EversourceTariffParseError,
    EversourceUnsupportedTariffError,
)

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


def test_dual_fetch_uses_only_explicit_segment_cookie() -> None:
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(EversourceClient(session, "nh", "r").async_get_rates())
    assert str(rates.total_variable_rate) == "0.25918"
    assert all(
        call[1]["headers"] == {"Cookie": ".SEGMENT=nh"} for call in session.calls
    )


@pytest.mark.parametrize("status", [403, 404, 500])
def test_http_errors_fail_safely(status: int) -> None:
    with pytest.raises(EversourceConnectionError):
        asyncio.run(
            EversourceClient(
                FakeSession([FakeResponse(status, "no")]), "nh", "r"
            ).async_get_rates()
        )


def test_timeout_fails_safely() -> None:
    with pytest.raises(EversourceConnectionError, match="Timed out"):
        asyncio.run(EversourceClient(TimeoutSession(), "nh", "r").async_get_rates())


def test_unsupported_tariff_fails_before_network_access() -> None:
    """Reject a non-production tariff without attempting an HTTP request."""
    with pytest.raises(EversourceUnsupportedTariffError):
        asyncio.run(EversourceClient(FakeSession([]), "ct", "r").async_get_rates())


def test_malformed_supply_fails_safely() -> None:
    session = FakeSession(
        [
            FakeResponse(200, "<p>none</p>"),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    with pytest.raises(EversourceTariffParseError):
        asyncio.run(EversourceClient(session, "nh", "r").async_get_rates())
