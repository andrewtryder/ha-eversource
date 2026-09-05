"""Async public HTTP client for Eversource tariffs."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

import aiohttp

from .const import REQUEST_TIMEOUT_SECONDS
from .models import EversourceRates
from .parsers import EversourceParseError, parse_tariff
from .sources import TARIFF_SOURCES, TariffSource, get_tariff_source

_LOGGER = logging.getLogger(__name__)

# Logical territory + rate class pairs implemented by this client.
SUPPORTED_TARIFFS = frozenset(TARIFF_SOURCES)


class EversourceError(Exception):
    """Base exception for this client."""


class EversourceConnectionError(EversourceError):
    """Eversource could not be contacted or returned an HTTP error."""


class EversourceUnsupportedTariffError(EversourceError):
    """A requested territory/rate class is not implemented."""


class EversourceTariffParseError(EversourceError):
    """A tariff page was malformed, missing, or implausible."""


class EversourceClient:
    """Retrieve public tariff pages for one logical territory and rate class."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        territory: str,
        rate_class: str,
    ) -> None:
        """Initialize the client with Home Assistant's shared session.

        ``territory`` and ``rate_class`` identify the logical tariff. Fetch URLs
        and any optional Sitefinity ``.SEGMENT`` cookie come from ``TariffSource``.
        """
        self._session = session
        self._territory = territory
        self._rate_class = rate_class
        self._source: TariffSource | None = get_tariff_source(territory, rate_class)

    async def _async_fetch(self, url: str) -> str:
        headers: dict[str, str] = {}
        assert self._source is not None
        if self._source.segment is not None:
            headers["Cookie"] = f".SEGMENT={self._source.segment}"
        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            async with self._session.get(
                url,
                headers=headers,
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
        if self._source is None:
            raise EversourceUnsupportedTariffError("Unsupported Eversource tariff")
        source = self._source
        supply_html, delivery_html = await asyncio.gather(
            self._async_fetch(source.supply_url),
            self._async_fetch(source.delivery_url),
        )
        try:
            supply, delivery = parse_tariff(
                self._territory,
                self._rate_class,
                supply_html,
                delivery_html,
            )
        except EversourceParseError as err:
            raise EversourceTariffParseError(str(err)) from err
        rates = EversourceRates(
            territory=self._territory,
            rate_class=self._rate_class,
            supply=supply,
            delivery=delivery,
            source_supply_url=source.supply_url,
            source_delivery_url=source.delivery_url,
            retrieved_at=datetime.now(UTC),
        )
        if not Decimal("0") < rates.total_variable_rate < Decimal("2"):
            raise EversourceTariffParseError(
                "Total variable rate outside plausible range"
            )
        _LOGGER.debug(
            "Parsed Eversource %s %s tariff with %d delivery components",
            self._territory,
            self._rate_class,
            len(delivery.variable_components),
        )
        return rates
