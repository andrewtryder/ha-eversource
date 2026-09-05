"""Shared helpers for public Eversource HTML tariff parsers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"([+-]?\d+(?:\.\d+)?)")
_MINUS_TRANSLATION = str.maketrans(
    {
        "\u2212": "-",  # Unicode minus
        "\u2013": "-",  # en dash used as numeric sign
        "\u2014": "-",  # em dash used as numeric sign
    }
)
_SUMMARY_LABELS = frozenset(
    {
        "total",
        "subtotal",
        "delivery total",
        "total delivery",
        "total delivery rate",
        "total delivery rates",
        "total delivery charge",
        "total delivery charges",
        "total variable rate",
        "total variable rates",
        "total variable delivery",
        "total variable delivery rate",
        "total variable delivery rates",
    }
)
_SUMMARY_PATTERN = re.compile(
    r"^(?:total|subtotal)(?:\s+(?:variable|delivery))*(?:\s+(?:rate|rates|charge|charges))?$"
    r"|^delivery\s+total(?:\s+(?:rate|rates|charge|charges))?$"
)


class EversourceParseError(ValueError):
    """The public tariff page did not contain a safe, recognizable tariff."""


def decimal(value: str, context: str) -> Decimal:
    """Parse a decimal amount, failing closed on malformed input."""
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as err:
        raise EversourceParseError(f"Malformed {context}: {value!r}") from err


def component_key(label: str) -> str:
    """Slugify a delivery component label into a stable mapping key."""
    normalized = " ".join(label.lower().split())
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def is_summary_row(label: str) -> bool:
    """Return True for non-additive total/subtotal rows in a delivery table."""
    normalized = " ".join(label.lower().split())
    normalized = re.sub(r"\s*\([^)]*\)\s*$", "", normalized).strip()
    return normalized in _SUMMARY_LABELS or bool(_SUMMARY_PATTERN.fullmatch(normalized))


def parse_cell(value: str, label: str) -> tuple[Decimal, str]:
    """Parse a rate cell into (amount, unit) using exact decimals."""
    # Normalize typographic minus signs only inside the numeric cell text.
    normalized = " ".join(
        value.translate(_MINUS_TRANSLATION).replace("¢", " cents ").split()
    )
    number = _NUMBER.search(normalized.replace(",", ""))
    if number is None:
        raise EversourceParseError(f"Missing numeric rate for {label}")
    amount = decimal(number.group(1), f"rate for {label}")
    lower = normalized.lower()
    label_lower = label.lower()
    if "cent" in lower and "kwh" in lower:
        return amount / Decimal("100"), "USD/kWh"
    if "$" in normalized and ("month" in lower or "month" in label_lower):
        return amount, "USD/month"
    if "$" in normalized and ("kwh" in lower or "kwh" in label_lower):
        return amount, "USD/kWh"
    raise EversourceParseError(f"Unsupported or malformed unit for {label}: {value!r}")
