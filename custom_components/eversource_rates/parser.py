"""Semantic parsers for public Eversource tariff pages.

Territory-specific implementations live under ``parsers/``. This module
re-exports the New Hampshire Rate R helpers and shared parse error for
existing imports and developer tooling.
"""

from __future__ import annotations

from .parsers import EversourceParseError, parse_tariff
from .parsers.common import is_summary_row as _is_summary_row
from .parsers.nh import parse_delivery_html, parse_supply_html

__all__ = [
    "EversourceParseError",
    "_is_summary_row",
    "parse_delivery_html",
    "parse_supply_html",
    "parse_tariff",
]
