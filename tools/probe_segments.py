"""Non-brute-force probe of tariff segments verified for this project."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.eversource_rates.const import (  # noqa: E402
    DELIVERY_URL,
    SUPPLY_URL,
)

VERIFIED_SEGMENTS = {"New Hampshire": "nh"}


async def _probe(
    session: aiohttp.ClientSession, url: str, segment: str
) -> dict[str, object]:
    async with session.get(url, headers={"Cookie": f".SEGMENT={segment}"}) as response:
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
        for territory, segment in VERIFIED_SEGMENTS.items():
            supply, delivery = await asyncio.gather(
                _probe(session, SUPPLY_URL, segment),
                _probe(session, DELIVERY_URL, segment),
            )
            print(
                f"{territory} ({segment})\n  supply: {supply}\n  delivery: {delivery}"
            )


if __name__ == "__main__":
    asyncio.run(main())
