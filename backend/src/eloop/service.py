"""Application service: orchestrates stores, storage, classification and notifications."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from .auth import authenticate, authenticate_claims
from .catalog import BY_KEY, CATEGORIES
from .classifier import ClassifierChain
from .errors import ApiError, PickupNotFoundError, StateConflictError
from .ledger import build_event, verify_chain
from .matching import nearest_collector
from .models import (
    Area,
    ClassifyRequest,
    CollectRequest,
    Collector,
    Pickup,
    PickupRequest,
    UploadRequest,
)
from .notify import Notifier
from .storage import Storage, is_valid_key
from .store import Store
from .views import collector_view, public_view

_ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32: no I, L, O, U


def new_pickup_id() -> str:
    return "EL-" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(8))


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_collectors() -> dict[str, Collector]:
    raw = json.loads(resources.files("eloop.data").joinpath("collectors.json").read_text())
    return {c["id"]: Collector.model_validate(c) for c in raw}


def load_areas() -> list[Area]:
    raw = json.loads(resources.files("eloop.data").joinpath("areas.json").read_text())
    return [Area.model_validate(a) for a in raw]


@dataclass(frozen=True, slots=True)
class Limits:
    max_upload_bytes: int
    max_match_km: float


class PickupService:
    def __init__(
        self,
        *,
        store: Store,
        storage: Storage,
        classifier: ClassifierChain,
        notifier: Notifier,
        collectors: Mapping[str, Collector],
        areas: list[Area],
        collector_secret: str,
        limits: Limits,
        auth_mode: str = "hmac",
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], str] = new_pickup_id,
    ) -> None:
        self._store = store
        self._storage = storage
        self._classifier = classifier
        self._notifier = notifier
        self._collectors = dict(collectors)
        self._areas = areas
        self._secret = collector_secret
        self._auth_mode = auth_mode
        self._limits = limits
        self._clock = clock
        self._new_id = id_factory

    @property
    def storage(self) -> Storage:
        return self._storage

    def collector_ids(self) -> list[str]:
        return sorted(self._collectors)

    # -- reference data --------------------------------------------------------------------

    def meta(self) -> dict[str, Any]:
        return {
            "categories": [c.public() for c in CATEGORIES],
            "areas": [a.model_dump() for a in self._areas],
            "limits": {"max_upload_bytes": self._limits.max_upload_bytes},
        }

    # -- citizen flow ----------------------------------------------------------------------

    def start_upload(self, request: UploadRequest) -> dict[str, Any]:
        ticket = self._storage.create_upload(request.content_type)
        return {"url": ticket.url, "fields": ticket.fields, "key": ticket.key}

    def classify(self, request: ClassifyRequest) -> dict[str, Any]:
        if not is_valid_key(request.image_key) or not self._storage.exists(request.image_key):
            raise ApiError.unprocessable("IMAGE_NOT_FOUND", "Upload the image before classifying it")
        result = self._classifier.classify(request.image_key)
        return {
            "source": result.source,
            "predictions": [
                {"category": p.category, "confidence": round(p.confidence, 3)} for p in result.predictions
            ],
        }

    def create_pickup(self, request: PickupRequest) -> dict[str, Any]:
        category = BY_KEY.get(request.category)
        if category is None:
            raise ApiError.unprocessable("UNKNOWN_CATEGORY", "Choose a listed device category")
        if request.image_key is not None and (
            not is_valid_key(request.image_key) or not self._storage.exists(request.image_key)
        ):
            raise ApiError.unprocessable("IMAGE_NOT_FOUND", "The uploaded image could not be found")

        match = nearest_collector(
            self._collectors.values(), request.category, request.lat, request.lng, self._limits.max_match_km
        )
        if match is None:
            raise ApiError.unprocessable(
                "NO_COLLECTOR_IN_RANGE",
                "No collection point that accepts this item serves your location yet",
            )
        collector, distance_km = match

        now = iso(self._clock())
        for _ in range(3):  # a collision on a 40-bit random id is vanishingly rare; retry anyway
            pickup = Pickup(
                id=self._new_id(),
                status="requested",
                category=category.key,
                quantity=request.quantity,
                classified_by=request.classified_by,
                confidence=request.confidence,
                image_key=request.image_key,
                est_weight_g=category.typical_weight_g * request.quantity,
                value_inr_min=category.value_inr[0] * request.quantity,
                value_inr_max=category.value_inr[1] * request.quantity,
                contact_name=request.name,
                contact_phone=request.phone,
                address=request.address,
                lat=request.lat,
                lng=request.lng,
                area=request.area,
                collector_id=collector.id,
                distance_km=round(distance_km, 2),
                created_at=now,
                updated_at=now,
            )
            event = build_event(
                None,
                type_="requested",
                actor="citizen",
                data={
                    "category": category.key,
                    "quantity": request.quantity,
                    "collector_id": collector.id,
                    "classified_by": request.classified_by,
                },
                at=now,
            )
            try:
                self._store.create(pickup, event)
                break
            except StateConflictError:
                continue
        else:
            raise ApiError(503, "ID_GENERATION_FAILED", "Please try again")

        self._notifier.new_pickup(
            pickup_id=pickup.id,
            collector_id=collector.id,
            category=category.label,
            area=request.area or collector.area,
        )
        return self._track_view(pickup)

    def track(self, pickup_id: str) -> dict[str, Any]:
        pickup = self._store.get(pickup_id)
        if pickup is None:
            raise ApiError.not_found("Pickup")
        return self._track_view(pickup)

    def _track_view(self, pickup: Pickup) -> dict[str, Any]:
        events = self._store.events(pickup.id)
        return public_view(pickup, events, verify_chain(events), self._collectors.get(pickup.collector_id))

    def impact(self) -> dict[str, Any]:
        stats = self._store.stats()
        by_category = [
            {"category": key, "label": BY_KEY[key].label if key in BY_KEY else key, "grams": grams}
            for key, grams in sorted(stats.by_category_g.items(), key=lambda kv: kv[1], reverse=True)
        ]
        return {
            "pickups_total": stats.pickups_total,
            "pickups_collected": stats.pickups_collected,
            "collected_g": stats.collected_g,
            "by_category": by_category,
        }

    # -- collector flow --------------------------------------------------------------------

    def authenticate(self, headers: Mapping[str, str], claims: Mapping[str, str] | None = None) -> Collector:
        if self._auth_mode == "cognito":
            return authenticate_claims(claims or {}, self._collectors)  # never fall back to the shared-key path
        return authenticate(headers, self._secret, self._collectors)

    def collector_profile(self, collector: Collector) -> dict[str, Any]:
        return {"id": collector.id, "name": collector.name, "area": collector.area}

    def collector_queue(self, collector: Collector) -> dict[str, Any]:
        mine: list[Pickup] = []
        for status in ("requested", "confirmed"):
            mine.extend(p for p in self._store.list_by_status(status) if p.collector_id == collector.id)  # type: ignore[arg-type]
        mine.sort(key=lambda p: p.created_at)
        return {"pickups": [collector_view(p) for p in mine]}

    def _owned(self, collector: Collector, pickup_id: str) -> Pickup:
        pickup = self._store.get(pickup_id)
        # Same response for "missing" and "not yours" so ids cannot be probed.
        if pickup is None or pickup.collector_id != collector.id:
            raise ApiError.not_found("Pickup")
        return pickup

    def confirm(self, collector: Collector, pickup_id: str) -> dict[str, Any]:
        self._owned(collector, pickup_id)
        updated = self._advance(
            pickup_id,
            expected="requested",
            new="confirmed",
            event_type="confirmed",
            actor=f"collector:{collector.id}",
            data={"collector_id": collector.id},
            changes={},
        )
        return collector_view(updated)

    def collect(self, collector: Collector, pickup_id: str, request: CollectRequest) -> dict[str, Any]:
        pickup = self._owned(collector, pickup_id)
        updated = self._advance(
            pickup_id,
            expected="confirmed",
            new="collected",
            event_type="collected",
            actor=f"collector:{collector.id}",
            data={"collector_id": collector.id, "category": pickup.category, "weight_g": request.weight_g},
            changes={"collected_weight_g": request.weight_g},
        )
        return collector_view(updated)

    def _advance(
        self,
        pickup_id: str,
        *,
        expected: str,
        new: str,
        event_type: str,
        actor: str,
        data: Mapping[str, Any],
        changes: Mapping[str, Any],
    ) -> Pickup:
        try:
            updated, _ = self._store.advance(
                pickup_id,
                expected_status=expected,  # type: ignore[arg-type]
                new_status=new,  # type: ignore[arg-type]
                event_type=event_type,
                actor=actor,
                data=data,
                at=iso(self._clock()),
                changes=changes,
            )
        except PickupNotFoundError as exc:
            raise ApiError.not_found("Pickup") from exc
        except StateConflictError as exc:
            raise ApiError.conflict(f"This pickup can no longer be moved to '{new}'") from exc
        return updated
