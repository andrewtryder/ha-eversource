"""Non-brute-force probe of configured public tariff URLs."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.eversource_rates.sources import get_tariff_source  # noqa: E402

VERIFIED_TARIFFS = {"New Hampshire": ("nh", "r")}


async def _probe(session: aiohttp.ClientSession, url: str) -> dict[str, object]:
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        detected_territory = (
            "New Hampshire" if "new hampshire" in html.lower() else None
        )
        return {
            "status": response.status,
            "final_url": str(response.url),
            "title": soup.title.get_text(strip=True) if soup.title else None,
            "detected_territory": detected_territory,
            "supply_content": "current supply rates" in html.lower()
            and "rate r" in html.lower(),
            "delivery_table": "delivery component" in html.lower()
            and "customer charge" in html.lower(),
        }


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        for territory, selection in VERIFIED_TARIFFS.items():
            source = get_tariff_source(*selection)
            assert source is not None
            supply, delivery = await asyncio.gather(
                _probe(session, source.supply_url),
                _probe(session, source.delivery_url),
            )
            print(f"{territory}\n  supply: {supply}\n  delivery: {delivery}")


if __name__ == "__main__":
    asyncio.run(main())
