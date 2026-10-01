"""Data models for Eversource public outage monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EversourceOutageArea:
    """Current public outage snapshot for one municipality."""

    territory: str
    area_name: str
    customers_out: int
    customers_served: int
    percent_out: float | None
    source_url: str
    retrieved_at: datetime
