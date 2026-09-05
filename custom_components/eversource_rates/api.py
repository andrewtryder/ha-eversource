"""Async public HTTP client for Eversource tariffs."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

import aiohttp

from .const import DELIVERY_URL, REQUEST_TIMEOUT_SECONDS, SUPPLY_URL
from .models import EversourceRates
from .parser import EversourceParseError, parse_delivery_html, parse_supply_html

_LOGGER = logging.getLogger(__name__)


class EversourceError(Exception):
    """Base exception for this client."""


class EversourceConnectionError(EversourceError):
    """Eversource could not be contacted or returned an HTTP error."""


class EversourceUnsupportedTariffError(EversourceError):
    """A requested territory/rate class is not implemented."""


class EversourceTariffParseError(EversourceError):
    """A tariff page was malformed, missing, or implausible."""


class EversourceClient:
    """Retrieve public, server-rendered tariff pages using an explicit segment."""

    def __init__(
        self, session: aiohttp.ClientSession, segment: str, rate_class: str
    ) -> None:
        """Initialize the client with Home Assistant's shared session."""
        self._session = session
        self._segment = segment
        self._rate_class = rate_class

    async def _async_fetch(self, url: str) -> str:
        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            async with self._session.get(
                url,
                headers={"Cookie": f".SEGMENT={self._segment}"},
                timeout=timeout,
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    raise EversourceConnectionError(
                        f"HTTP {response.status} retrieving tariff page"
                    )
                return await response.text()
        except TimeoutError as err:
            raise EversourceConnectionError("Timed out retrieving tariff page") from err
        except aiohttp.ClientError as err:
            raise EversourceConnectionError("Unable to retrieve tariff page") from err

    async def async_get_rates(self) -> EversourceRates:
        """Fetch supply and delivery concurrently and validate the parsed tariff."""
        if (self._segment, self._rate_class) != ("nh", "r"):
            raise EversourceUnsupportedTariffError("Unsupported Eversource tariff")
        supply_html, delivery_html = await asyncio.gather(
            self._async_fetch(SUPPLY_URL), self._async_fetch(DELIVERY_URL)
        )
        try:
            supply = parse_supply_html(supply_html, self._rate_class)
            delivery = parse_delivery_html(delivery_html)
        except EversourceParseError as err:
            raise EversourceTariffParseError(str(err)) from err
        rates = EversourceRates(
            territory="nh",
            rate_class=self._rate_class,
            supply=supply,
            delivery=delivery,
            source_supply_url=SUPPLY_URL,
            source_delivery_url=DELIVERY_URL,
            retrieved_at=datetime.now(UTC),
        )
        if not Decimal("0") < rates.total_variable_rate < Decimal("2"):
            raise EversourceTariffParseError(
                "Total variable rate outside plausible range"
            )
        _LOGGER.debug(
            "Parsed Eversource NH Rate R tariff with %d delivery components",
            len(delivery.variable_components),
        )
        return rates
