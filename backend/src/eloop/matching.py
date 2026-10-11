"""Geographic matching of a pickup to the nearest suitable collection point."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .models import Collector

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_collector(
    collectors: Iterable[Collector], category: str, lat: float, lng: float, max_km: float
) -> tuple[Collector, float] | None:
    best: tuple[Collector, float] | None = None
    for collector in collectors:
        if not collector.accepts_category(category):
            continue
        distance = haversine_km(lat, lng, collector.lat, collector.lng)
        if distance <= max_km and (best is None or distance < best[1]):
            best = (collector, distance)
    return best
