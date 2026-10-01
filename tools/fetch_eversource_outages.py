"""Fetch Eversource outage reports for manual verification."""

from __future__ import annotations

import argparse
import asyncio
import ssl
import sys
from pathlib import Path

import aiohttp

try:
    import certifi

    ssl_context: ssl.SSLContext | None = ssl.create_default_context(
        cafile=certifi.where()
    )
except ImportError:
    ssl_context = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.eversource_rates.const import TERRITORIES
from custom_components.eversource_rates.outage_api import EversourceOutageClient


async def _fetch_and_display(territory: str, municipality: str | None = None) -> None:
    connector = aiohttp.TCPConnector(ssl=ssl_context) if ssl_context else None
    async with aiohttp.ClientSession(connector=connector) as session:
        client = EversourceOutageClient(session)
        if municipality:
            area = await client.async_get_area(territory, municipality)
            print(f"Territory: {area.territory}")
            print(f"Municipality: {area.area_name}")
            print(f"Customers Out: {area.customers_out}")
            print(f"Customers Served: {area.customers_served}")
            print(f"Percent Out: {area.percent_out}")
            print(f"Retrieved At: {area.retrieved_at.isoformat()}")
            print(f"Source URL: {area.source_url}")
        else:
            areas = await client.async_list_areas(territory)
            print(f"Territory: {territory} ({len(areas)} municipalities found)")
            for _norm_name, area in sorted(areas.items()):
                pct = area.percent_out or 0.0
                print(
                    f"  {area.area_name:<25} "
                    f"Out: {area.customers_out:>5} / "
                    f"Served: {area.customers_served:>7} ({pct:.2f}%)"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Eversource public outage report."
    )
    parser.add_argument(
        "--territory",
        choices=list(TERRITORIES.keys()),
        default="nh",
        help="Service territory (default: nh)",
    )
    parser.add_argument(
        "--municipality",
        type=str,
        default=None,
        help="Optional municipality name to fetch",
    )
    args = parser.parse_args()
    asyncio.run(_fetch_and_display(args.territory, args.municipality))


if __name__ == "__main__":
    main()
