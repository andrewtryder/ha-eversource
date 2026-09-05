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
from .tariffs import TariffSelection

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
    """Retrieve public tariff pages for one logical tariff selection."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        selection: TariffSelection | None = None,
        territory: str | None = None,
        rate_class: str | None = None,
        supply_plan: str | None = None,
        service_area: str | None = None,
    ) -> None:
        """Initialize the client with Home Assistant's shared session.

        Prefer ``selection=``. Keyword ``territory`` / ``rate_class`` /
        ``supply_plan`` / ``service_area`` remain for call-site convenience.
        """
        if selection is None:
            if territory is None or rate_class is None:
                raise TypeError(
                    "EversourceClient requires selection= or territory= and rate_class="
                )
            selection = TariffSelection(
                territory=territory,
                rate_class=rate_class,
                supply_plan=supply_plan,
                service_area=service_area,
            )
        self._session = session
        self._selection = selection
        self._source: TariffSource | None = get_tariff_source(
            selection.territory, selection.rate_class
        )

    @property
    def selection(self) -> TariffSelection:
        """Return the logical tariff selection for this client."""
        return self._selection

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
        selection = self._selection
        supply_html, delivery_html = await asyncio.gather(
            self._async_fetch(source.supply_url),
            self._async_fetch(source.delivery_url),
        )
        try:
            supply, delivery = parse_tariff(
                selection,
                supply_html,
                delivery_html,
            )
        except EversourceParseError as err:
            raise EversourceTariffParseError(str(err)) from err
        rates = EversourceRates(
            territory=selection.territory,
            rate_class=selection.rate_class,
            supply=supply,
            delivery=delivery,
            source_supply_url=source.supply_url,
            source_delivery_url=source.delivery_url,
            retrieved_at=datetime.now(UTC),
            supply_plan=selection.supply_plan,
            service_area=selection.service_area,
        )
        if not Decimal("0") < rates.total_variable_rate < Decimal("2"):
            raise EversourceTariffParseError(
                "Total variable rate outside plausible range"
            )
        _LOGGER.debug(
            "Parsed Eversource %s %s tariff with %d delivery components",
            selection.territory,
            selection.rate_class,
            len(delivery.variable_components),
        )
        return rates
