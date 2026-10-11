"""Response shaping. The tracking code is a bearer secret, so public views carry no personal data."""

from __future__ import annotations

from typing import Any

from .catalog import BY_KEY
from .models import Collector, Event, Pickup


def _category_fields(pickup: Pickup) -> dict[str, Any]:
    category = BY_KEY[pickup.category]
    return {"category": pickup.category, "category_label": category.label}


def public_view(
    pickup: Pickup, events: list[Event], verified: bool, collector: Collector | None
) -> dict[str, Any]:
    return {
        "id": pickup.id,
        "status": pickup.status,
        **_category_fields(pickup),
        "quantity": pickup.quantity,
        "area": pickup.area,
        "collector": {"name": collector.name, "area": collector.area} if collector else None,
        "created_at": pickup.created_at,
        "updated_at": pickup.updated_at,
        "est_weight_g": pickup.est_weight_g,
        "collected_weight_g": pickup.collected_weight_g,
        "chain_verified": verified,
        "head_hash": events[-1].hash if events else None,
        "events": [
            {"seq": e.seq, "type": e.type, "at": e.at, "actor": e.actor, "hash": e.hash} for e in events
        ],
    }


def collector_view(pickup: Pickup) -> dict[str, Any]:
    """Personal details are revealed only once the collector has accepted the pickup."""
    category = BY_KEY[pickup.category]
    view: dict[str, Any] = {
        "id": pickup.id,
        "status": pickup.status,
        **_category_fields(pickup),
        "quantity": pickup.quantity,
        "area": pickup.area,
        "distance_km": round(pickup.distance_km, 1),
        "est_weight_g": pickup.est_weight_g,
        "hazard": category.hazard,
        "handling": category.handling,
        "created_at": pickup.created_at,
        "collected_weight_g": pickup.collected_weight_g,
        "contact": None,
    }
    if pickup.status != "requested":
        view["contact"] = {
            "name": pickup.contact_name,
            "phone": pickup.contact_phone,
            "address": pickup.address,
            "lat": pickup.lat,
            "lng": pickup.lng,
        }
    return view
