"""Deterministic Home Assistant object-ID helpers for tariff sensors."""

from __future__ import annotations

import re

# Existing NH Rate R entity object IDs are part of the documented public contract.
_LEGACY_NH_RATE_R = ("nh", "r")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_object_id_part(value: str) -> str:
    """Normalize a territory, rate-class, or sensor key for an object ID."""
    slug = _NON_ALNUM.sub("_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError(f"Cannot derive object-id part from {value!r}")
    return slug


def sensor_object_id(territory: str, rate_class: str, sensor_key: str) -> str:
    """Return the sensor object ID for a territory/rate-class/sensor combination.

    New Hampshire Rate R keeps the historical short IDs used by existing
    installs and documentation. Every other combination includes territory and
    rate class so concurrent config entries cannot collide.
    """
    key = slugify_object_id_part(sensor_key)
    territory_slug = slugify_object_id_part(territory)
    rate_class_slug = slugify_object_id_part(rate_class)
    if (territory_slug, rate_class_slug) == _LEGACY_NH_RATE_R:
        return f"eversource_{key}"
    return f"eversource_{territory_slug}_{rate_class_slug}_{key}"
