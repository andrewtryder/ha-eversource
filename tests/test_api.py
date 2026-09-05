"""Offline HTTP client behavior tests."""

import asyncio
from pathlib import Path

import pytest

from custom_components.eversource_rates.api import (
    SUPPORTED_TARIFFS,
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


def _client(
    session, *, territory="nh", segment="nh", rate_class="r"
) -> EversourceClient:
    return EversourceClient(
        session,
        territory=territory,
        segment=segment,
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
    assert all(
        call[1]["headers"] == {"Cookie": ".SEGMENT=nh"} for call in session.calls
    )


def test_logical_territory_can_differ_from_sitefinity_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP uses segment; models and support checks use logical territory."""
    monkeypatch.setattr(
        "custom_components.eversource_rates.api.SUPPORTED_TARIFFS",
        frozenset({*SUPPORTED_TARIFFS, ("synthetic", "r")}),
    )
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(
        _client(
            session,
            territory="synthetic",
            segment="completely-different-segment",
            rate_class="r",
        ).async_get_rates()
    )
    assert rates.territory == "synthetic"
    assert all(
        call[1]["headers"] == {"Cookie": ".SEGMENT=completely-different-segment"}
        for call in session.calls
    )


def test_support_dispatch_uses_logical_territory_not_segment() -> None:
    """A mismatched segment must not change unsupported-tariff decisions."""
    # Logical territory unsupported even when segment looks like NH.
    with pytest.raises(EversourceUnsupportedTariffError):
        asyncio.run(
            _client(
                FakeSession([]),
                territory="ct",
                segment="nh",
                rate_class="r",
            ).async_get_rates()
        )
    # Logical NH remains supported even with a non-nh segment cookie value.
    session = FakeSession(
        [
            FakeResponse(200, (FIXTURES / "sanitized_supply.html").read_text()),
            FakeResponse(200, (FIXTURES / "sanitized_delivery.html").read_text()),
        ]
    )
    rates = asyncio.run(
        _client(
            session,
            territory="nh",
            segment="sitefinity-nh",
            rate_class="r",
        ).async_get_rates()
    )
    assert rates.territory == "nh"
    assert session.calls[0][1]["headers"] == {"Cookie": ".SEGMENT=sitefinity-nh"}


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
            _client(FakeSession([]), territory="ct", segment="ct").async_get_rates()
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
