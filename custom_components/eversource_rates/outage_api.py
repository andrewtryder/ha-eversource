"""Public async HTTP client for Eversource outage reports."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import (
    OUTAGE_BASE_URL,
    OUTAGE_REPORT_FILES,
    REQUEST_TIMEOUT_SECONDS,
)
from .outage_models import EversourceOutageArea

_LOGGER = logging.getLogger(__name__)


class EversourceOutageError(Exception):
    """Base exception for outage retrieval and parsing errors."""


class EversourceOutageConnectionError(EversourceOutageError):
    """Network connection or HTTP error communicating with Eversource outage service."""


class EversourceOutageParseError(EversourceOutageError):
    """Malformed or invalid outage JSON structure."""


def normalize_municipality_name(name: str) -> str:
    """Normalize municipality name for consistent matching."""
    return name.strip().upper()


def _parse_leaf_counts(node: dict[str, Any], area_name: str) -> tuple[int, int]:
    """Validate and extract customer counts for a municipality leaf."""
    cust_a = node.get("cust_a")
    if not isinstance(cust_a, dict) or "val" not in cust_a:
        raise EversourceOutageParseError(
            f"Leaf area {area_name} missing cust_a.val object"
        )

    cust_a_val = cust_a["val"]
    if (
        not isinstance(cust_a_val, int)
        or isinstance(cust_a_val, bool)
        or cust_a_val < 0
    ):
        raise EversourceOutageParseError(
            f"Leaf area {area_name} invalid cust_a.val: {cust_a_val}"
        )

    cust_s = node.get("cust_s")
    if not isinstance(cust_s, int) or isinstance(cust_s, bool) or cust_s < 0:
        raise EversourceOutageParseError(
            f"Leaf area {area_name} invalid cust_s: {cust_s}"
        )

    if cust_s > 0 and cust_a_val > cust_s:
        raise EversourceOutageParseError(
            f"Leaf area {area_name} customers out ({cust_a_val}) "
            f"exceeds served ({cust_s})"
        )

    return cust_a_val, cust_s


def _parse_leaf_percent(node: dict[str, Any], area_name: str) -> float | None:
    """Validate and extract percent out for a municipality leaf."""
    percent_out = node.get("percent_out")
    if percent_out is None:
        return None
    if isinstance(percent_out, bool) or not isinstance(percent_out, int | float):
        raise EversourceOutageParseError(
            f"Leaf area {area_name} percent_out is non-numeric: {percent_out}"
        )
    parsed_percent = float(percent_out)
    if parsed_percent < 0 or parsed_percent > 100:
        raise EversourceOutageParseError(
            f"Leaf area {area_name} percent_out outside plausible range "
            f"[0, 100]: {parsed_percent}"
        )
    return parsed_percent


def _parse_leaf_node(
    node: dict[str, Any],
    territory: str,
    source_url: str,
    retrieved_at: datetime,
) -> EversourceOutageArea:
    """Parse and validate a single leaf municipality node."""
    area_name = node.get("area_name")
    if not isinstance(area_name, str) or not area_name.strip():
        raise EversourceOutageParseError("Leaf area missing valid area_name")

    name = area_name.strip()
    cust_out, cust_served = _parse_leaf_counts(node, name)
    percent_out = _parse_leaf_percent(node, name)

    return EversourceOutageArea(
        territory=territory,
        area_name=name,
        customers_out=cust_out,
        customers_served=cust_served,
        percent_out=percent_out,
        source_url=source_url,
        retrieved_at=retrieved_at,
    )


def _collect_leaf_areas(
    node: Any,
    territory: str,
    source_url: str,
    retrieved_at: datetime,
    out: dict[str, EversourceOutageArea],
) -> None:
    """Recursively traverse the outage tree and collect municipality leaf areas."""
    if not isinstance(node, dict):
        raise EversourceOutageParseError("Area node is not a JSON object")

    children = node.get("areas")
    if isinstance(children, list) and children:
        for child in children:
            _collect_leaf_areas(child, territory, source_url, retrieved_at, out)
        return

    area = _parse_leaf_node(node, territory, source_url, retrieved_at)
    norm_name = normalize_municipality_name(area.area_name)
    if norm_name in out:
        raise EversourceOutageParseError(
            f"Ambiguous duplicate municipality '{norm_name}' in {territory} report"
        )
    out[norm_name] = area


class EversourceOutageClient:
    """Client for retrieving public Eversource outage snapshots."""

    @staticmethod
    def get_report_filename(territory: str) -> str:
        """Get the report filename for a service territory."""
        if territory not in OUTAGE_REPORT_FILES:
            raise EversourceOutageError(f"Unsupported outage territory: {territory}")
        return OUTAGE_REPORT_FILES[territory]

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize with Home Assistant's shared aiohttp ClientSession."""
        self._session = session

    async def _async_fetch_json(self, url: str) -> Any:
        """Fetch and parse JSON from a public URL."""
        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            async with self._session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    raise EversourceOutageConnectionError(
                        f"HTTP {response.status} retrieving {url}"
                    )
                return await response.json(content_type=None)
        except TimeoutError as err:
            raise EversourceOutageConnectionError(
                "Timed out retrieving outage data"
            ) from err
        except (ValueError, TypeError, json.JSONDecodeError) as err:
            raise EversourceOutageParseError(
                f"Malformed JSON from {url}: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise EversourceOutageConnectionError(
                "Unable to retrieve outage data"
            ) from err

    async def async_fetch_metadata(self) -> str:
        """Fetch metadata.json and return the active generation directory."""
        metadata_url = f"{OUTAGE_BASE_URL}/metadata.json"
        data = await self._async_fetch_json(metadata_url)
        if not isinstance(data, dict):
            raise EversourceOutageParseError("metadata.json is not a JSON object")

        directory = data.get("directory") or data.get("Directory")
        if not isinstance(directory, str) or not directory.strip():
            raise EversourceOutageParseError(
                "metadata.json missing valid 'directory' or 'Directory' string"
            )
        return directory.strip()

    async def async_list_areas(self, territory: str) -> dict[str, EversourceOutageArea]:
        """Fetch and parse all municipality leaf areas for a territory."""
        territory_key = territory.lower()
        report_file = OUTAGE_REPORT_FILES.get(territory_key)
        if not report_file:
            raise EversourceOutageParseError(
                f"Unsupported outage territory: {territory}"
            )

        directory = await self.async_fetch_metadata()
        report_url = f"{OUTAGE_BASE_URL}/{directory}/{report_file}"
        data = await self._async_fetch_json(report_url)

        if not isinstance(data, dict):
            raise EversourceOutageParseError("Outage report is not a JSON object")

        file_data = data.get("file_data")
        if not isinstance(file_data, dict):
            raise EversourceOutageParseError("Outage report missing file_data object")

        top_areas = file_data.get("areas")
        if not isinstance(top_areas, list) or not top_areas:
            raise EversourceOutageParseError(
                "Outage report missing file_data.areas list"
            )

        areas_by_name: dict[str, EversourceOutageArea] = {}
        retrieved_at = datetime.now(UTC)

        for top_node in top_areas:
            _collect_leaf_areas(
                top_node, territory_key, report_url, retrieved_at, areas_by_name
            )

        if not areas_by_name:
            raise EversourceOutageParseError(
                f"No municipality leaves found in {territory} report"
            )

        _LOGGER.debug(
            "Parsed %d municipality leaves from %s report (%s)",
            len(areas_by_name),
            territory_key,
            report_file,
        )
        return areas_by_name

    async def async_get_area(
        self, territory: str, municipality: str
    ) -> EversourceOutageArea:
        """Fetch and return the outage snapshot for a specific municipality."""
        areas = await self.async_list_areas(territory)
        norm_name = normalize_municipality_name(municipality)
        area = areas.get(norm_name)
        if area is None:
            raise EversourceOutageParseError(
                f"Configured municipality '{municipality}' not found in "
                f"{territory} outage report"
            )
        return area
