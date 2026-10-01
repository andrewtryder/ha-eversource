"""Tests for the Eversource public outage API client and parser."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.eversource_rates.outage_api import (
    EversourceOutageClient,
    EversourceOutageConnectionError,
    EversourceOutageError,
    EversourceOutageParseError,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    """Mock aiohttp response."""

    def __init__(
        self,
        status: int = 200,
        data: dict | list | str | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.status = status
        self._data = data
        self._content_type = content_type

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def json(self, content_type=None):
        if isinstance(self._data, (dict, list)):
            return self._data
        if isinstance(self._data, str):
            return json.loads(self._data)
        raise ValueError("Invalid JSON data")

    async def text(self):
        if isinstance(self._data, str):
            return self._data
        return json.dumps(self._data)


class FakeSession:
    """Mock aiohttp client session."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        if not self.responses:
            raise RuntimeError(f"No response queued for {url}")
        return self.responses.pop(0)


def _load_fixture(filename: str) -> dict:
    with open(FIXTURES / filename, encoding="utf-8") as f:
        return json.load(f)


async def test_territory_report_filename_mapping() -> None:
    """All 4 supported territories map to their expected report files."""
    session = MagicMock()
    client = EversourceOutageClient(session)

    assert client.get_report_filename("nh") == "report_hampshire.json"
    assert client.get_report_filename("ct") == "report_conn.json"
    assert client.get_report_filename("ema") == "report_east.json"
    assert client.get_report_filename("wma") == "report_west.json"

    with pytest.raises(EversourceOutageError, match="Unsupported outage territory"):
        client.get_report_filename("invalid")


async def test_metadata_parsing_success() -> None:
    """Metadata correctly extracts directory attribute."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    session = FakeSession([FakeResponse(200, meta_json)])
    client = EversourceOutageClient(session)

    directory = await client.async_fetch_metadata()
    assert directory == "2026_10_01_12_00_00"


async def test_metadata_parsing_capital_directory() -> None:
    """Metadata accepts capitalized Directory attribute for compatibility."""
    meta_json = {"Directory": "2026_10_01_12_00_00"}
    session = FakeSession([FakeResponse(200, meta_json)])
    client = EversourceOutageClient(session)

    directory = await client.async_fetch_metadata()
    assert directory == "2026_10_01_12_00_00"


@pytest.mark.parametrize(
    "invalid_meta",
    [
        {},
        {"directory": ""},
        {"directory": "   "},
        {"directory": 12345},
        {"other_key": "val"},
    ],
)
async def test_metadata_parsing_invalid(invalid_meta: dict) -> None:
    """Missing or empty directory raises EversourceOutageParseError."""
    session = FakeSession([FakeResponse(200, invalid_meta)])
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageParseError, match="directory"):
        await client.async_fetch_metadata()


async def test_metadata_http_error() -> None:
    """HTTP 500 or 404 on metadata raises EversourceOutageConnectionError."""
    session = FakeSession([FakeResponse(500, "Internal Server Error")])
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageConnectionError):
        await client.async_fetch_metadata()


async def test_report_http_error() -> None:
    """HTTP error on territory report raises EversourceOutageConnectionError."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(404, "Not Found"),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageConnectionError):
        await client.async_list_areas("nh")


async def test_client_connection_exception_handled() -> None:
    """aiohttp ClientError or TimeoutError maps to EversourceOutageConnectionError."""
    session = MagicMock()
    session.get.side_effect = aiohttp.ClientConnectionError("Connection refused")
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageConnectionError):
        await client.async_fetch_metadata()


async def test_client_json_decode_error_handled() -> None:
    """Invalid JSON response maps to EversourceOutageParseError."""
    response = MagicMock()
    response.status = 200
    response.json = MagicMock(side_effect=json.JSONDecodeError("Invalid JSON", "{", 0))
    session = MagicMock()
    session.get.return_value.__aenter__.return_value = response
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageParseError):
        await client.async_fetch_metadata()


async def test_nh_fixture_listing_and_area() -> None:
    """NH fixture parses expected municipalities and values."""
    meta_json = _load_fixture("outage_metadata.json")
    nh_json = _load_fixture("outage_nh.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, nh_json),
        ]
    )
    client = EversourceOutageClient(session)

    areas = await client.async_list_areas("nh")
    assert "CONCORD" in areas
    assert "MANCHESTER" in areas
    assert "NASHUA" in areas

    concord = areas["CONCORD"]
    assert concord.area_name == "CONCORD"
    assert concord.customers_out == 12
    assert concord.customers_served == 19000
    assert concord.percent_out == 0.063
    assert concord.territory == "nh"

    manchester = areas["MANCHESTER"]
    assert manchester.customers_out == 0
    assert manchester.customers_served == 45000
    assert manchester.percent_out == 0.0


async def test_ct_fixture_listing() -> None:
    """CT fixture parses expected municipalities."""
    meta_json = _load_fixture("outage_metadata.json")
    ct_json = _load_fixture("outage_ct.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, ct_json),
        ]
    )
    client = EversourceOutageClient(session)

    areas = await client.async_list_areas("ct")
    assert "HARTFORD" in areas
    assert "STAMFORD" in areas
    assert areas["HARTFORD"].customers_out == 25
    assert areas["STAMFORD"].customers_out == 0


async def test_ema_fixture_listing() -> None:
    """EMA fixture parses expected municipalities."""
    meta_json = _load_fixture("outage_metadata.json")
    ema_json = _load_fixture("outage_ema.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, ema_json),
        ]
    )
    client = EversourceOutageClient(session)

    areas = await client.async_list_areas("ema")
    assert "BOSTON" in areas
    assert "CAMBRIDGE" in areas
    assert areas["BOSTON"].customers_out == 10
    assert areas["CAMBRIDGE"].customers_out == 0


async def test_wma_fixture_listing() -> None:
    """WMA fixture parses expected municipalities."""
    meta_json = _load_fixture("outage_metadata.json")
    wma_json = _load_fixture("outage_wma.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, wma_json),
        ]
    )
    client = EversourceOutageClient(session)

    areas = await client.async_list_areas("wma")
    assert "SPRINGFIELD" in areas
    assert "AMHERST" in areas
    assert areas["SPRINGFIELD"].customers_out == 8
    assert areas["AMHERST"].customers_out == 0


async def test_async_get_area_success() -> None:
    """async_get_area retrieves the requested municipality case-insensitively."""
    meta_json = _load_fixture("outage_metadata.json")
    nh_json = _load_fixture("outage_nh.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, nh_json),
        ]
    )
    client = EversourceOutageClient(session)

    area = await client.async_get_area("nh", "concord")
    assert area.area_name == "CONCORD"
    assert area.customers_out == 12
    assert "report_hampshire.json" in area.source_url
    assert area.retrieved_at is not None


async def test_async_get_area_missing_raises() -> None:
    """async_get_area raises EversourceOutageParseError if municipality is missing."""
    meta_json = _load_fixture("outage_metadata.json")
    nh_json = _load_fixture("outage_nh.json")
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, nh_json),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(
        EversourceOutageParseError,
        match="Configured municipality 'NONEXISTENT' not found",
    ):
        await client.async_get_area("nh", "NONEXISTENT")


@pytest.mark.parametrize(
    "malformed_report",
    [
        {},
        {"file_data": "not_a_dict"},
        {"file_data": {}},
        {"file_data": {"areas": "not_a_list"}},
        {"file_data": {"areas": []}},
    ],
)
async def test_malformed_report_structure(malformed_report: dict) -> None:
    """Report without valid file_data.areas raises EversourceOutageParseError."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, malformed_report),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageParseError):
        await client.async_list_areas("nh")


@pytest.mark.parametrize(
    "malformed_leaf",
    [
        {"cust_a": {"val": 5}, "cust_s": 100},  # missing area_name
        {"area_name": "", "cust_a": {"val": 5}, "cust_s": 100},  # empty area_name
        {"area_name": "TOWN", "cust_s": 100},  # missing cust_a
        {"area_name": "TOWN", "cust_a": {}, "cust_s": 100},  # missing val
        {"area_name": "TOWN", "cust_a": {"val": -1}, "cust_s": 100},  # negative out
        {"area_name": "TOWN", "cust_a": {"val": "five"}, "cust_s": 100},  # non-numeric
        {"area_name": "TOWN", "cust_a": {"val": 5}},  # missing cust_s
        {"area_name": "TOWN", "cust_a": {"val": 5}, "cust_s": -10},  # negative served
        {
            "area_name": "TOWN",
            "cust_a": {"val": 150},
            "cust_s": 100,
        },  # out exceeds served
        {
            "area_name": "TOWN",
            "cust_a": {"val": 5},
            "cust_s": 100,
            "percent_out": -1.0,
        },  # negative percent
        {
            "area_name": "TOWN",
            "cust_a": {"val": 5},
            "cust_s": 100,
            "percent_out": 150.0,
        },  # > 100 percent
        {
            "area_name": "TOWN",
            "cust_a": {"val": 5},
            "cust_s": 100,
            "percent_out": "bad",
        },  # non-numeric percent
        {
            "area_name": "TOWN",
            "cust_a": {"val": 5},
            "cust_s": 100,
            "percent_out": float("nan"),
        },  # NaN percent
        {
            "area_name": "TOWN",
            "cust_a": {"val": 5},
            "cust_s": 100,
            "percent_out": float("inf"),
        },  # infinite percent
    ],
)
async def test_malformed_leaf_fails_closed(malformed_leaf: dict) -> None:
    """Malformed leaf data fails closed with EversourceOutageParseError."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    report = {"file_data": {"areas": [malformed_leaf]}}
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, report),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(EversourceOutageParseError):
        await client.async_list_areas("nh")


async def test_duplicate_municipality_fails_closed() -> None:
    """Duplicate leaf names in the same territory fail closed."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    report = {
        "file_data": {
            "areas": [
                {"area_name": "CONCORD", "cust_a": {"val": 0}, "cust_s": 100},
                {"area_name": "CONCORD", "cust_a": {"val": 2}, "cust_s": 200},
            ]
        }
    }
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, report),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(
        EversourceOutageParseError, match="Ambiguous duplicate municipality 'CONCORD'"
    ):
        await client.async_list_areas("nh")


async def test_intermediate_nodes_not_exposed_as_municipalities() -> None:
    """Intermediate nodes containing children are not treated as selectable leaves."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    report = {
        "file_data": {
            "areas": [
                {
                    "area_name": "NORTH REGION",
                    "cust_a": {"val": 5},
                    "cust_s": 500,
                    "areas": [
                        {
                            "area_name": "TOWN A",
                            "cust_a": {"val": 2},
                            "cust_s": 200,
                        },
                        {
                            "area_name": "TOWN B",
                            "cust_a": {"val": 3},
                            "cust_s": 300,
                        },
                    ],
                }
            ]
        }
    }
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, report),
        ]
    )
    client = EversourceOutageClient(session)

    areas = await client.async_list_areas("nh")
    assert "NORTH REGION" not in areas
    assert "TOWN A" in areas
    assert "TOWN B" in areas


@pytest.mark.parametrize("invalid_areas", [{}, "not_a_list", 123])
async def test_node_with_malformed_areas_container_fails_closed(
    invalid_areas: object,
) -> None:
    """Node with non-list areas attribute fails closed with parse error."""
    meta_json = {"directory": "2026_10_01_12_00_00"}
    report = {
        "file_data": {
            "areas": [
                {
                    "area_name": "TOWN A",
                    "cust_a": {"val": 2},
                    "cust_s": 200,
                    "areas": invalid_areas,
                }
            ]
        }
    }
    session = FakeSession(
        [
            FakeResponse(200, meta_json),
            FakeResponse(200, report),
        ]
    )
    client = EversourceOutageClient(session)

    with pytest.raises(
        EversourceOutageParseError, match="has invalid 'areas' container"
    ):
        await client.async_list_areas("nh")
