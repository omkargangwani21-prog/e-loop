"""Persistence interface plus an in-memory implementation for local development and tests."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from .errors import PickupNotFoundError, StateConflictError
from .ledger import build_event
from .models import Event, Pickup, Scalar, Stats, Status


class Store(Protocol):
    def create(self, pickup: Pickup, event: Event) -> None: ...

    def get(self, pickup_id: str) -> Pickup | None: ...

    def events(self, pickup_id: str) -> list[Event]: ...

    def list_by_status(self, status: Status, limit: int = 100) -> list[Pickup]: ...

    def advance(
        self,
        pickup_id: str,
        *,
        expected_status: Status,
        new_status: Status,
        event_type: str,
        actor: str,
        data: Mapping[str, Scalar],
        at: str,
        changes: Mapping[str, Any],
    ) -> tuple[Pickup, Event]:
        """Atomically move a pickup to a new status and append the matching ledger event."""
        ...

    def stats(self) -> Stats: ...


class MemoryStore:
    """Thread-safe store. Optionally persists to a JSON file so the dev server survives restarts."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._pickups: dict[str, Pickup] = {}
        self._events: dict[str, list[Event]] = {}
        self._stats = Stats()
        self._path = Path(path) if path else None
        if self._path and self._path.is_file():
            self._load()

    # -- persistence -------------------------------------------------------------------------

    def _load(self) -> None:
        assert self._path is not None
        raw = json.loads(self._path.read_text())
        self._pickups = {k: Pickup.model_validate(v) for k, v in raw["pickups"].items()}
        self._events = {k: [Event.model_validate(e) for e in v] for k, v in raw["events"].items()}
        self._stats = Stats.model_validate(raw["stats"])

    def _flush(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pickups": {k: v.model_dump(mode="json") for k, v in self._pickups.items()},
            "events": {k: [e.model_dump(mode="json") for e in v] for k, v in self._events.items()},
            "stats": self._stats.model_dump(mode="json"),
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self._path)

    # -- Store ---------------------------------------------------------------------------------

    def create(self, pickup: Pickup, event: Event) -> None:
        with self._lock:
            if pickup.id in self._pickups:
                raise StateConflictError("pickup id already exists")
            self._pickups[pickup.id] = pickup
            self._events[pickup.id] = [event]
            self._stats.pickups_total += 1
            self._flush()

    def get(self, pickup_id: str) -> Pickup | None:
        with self._lock:
            return self._pickups.get(pickup_id)

    def events(self, pickup_id: str) -> list[Event]:
        with self._lock:
            return list(self._events.get(pickup_id, []))

    def list_by_status(self, status: Status, limit: int = 100) -> list[Pickup]:
        with self._lock:
            matches = [p for p in self._pickups.values() if p.status == status]
        matches.sort(key=lambda p: (p.created_at, p.id))
        return matches[:limit]

    def advance(
        self,
        pickup_id: str,
        *,
        expected_status: Status,
        new_status: Status,
        event_type: str,
        actor: str,
        data: Mapping[str, Scalar],
        at: str,
        changes: Mapping[str, Any],
    ) -> tuple[Pickup, Event]:
        with self._lock:
            pickup = self._pickups.get(pickup_id)
            if pickup is None:
                raise PickupNotFoundError(pickup_id)
            if pickup.status != expected_status:
                raise StateConflictError(f"pickup is {pickup.status}, expected {expected_status}")
            history = self._events[pickup_id]
            event = build_event(history[-1] if history else None, type_=event_type, actor=actor, data=data, at=at)
            updated = pickup.model_copy(
                update={**changes, "status": new_status, "updated_at": at, "version": pickup.version + 1}
            )
            self._pickups[pickup_id] = updated
            history.append(event)
            if new_status == "collected":
                self._stats.pickups_collected += 1
                self._stats.collected_g += updated.collected_weight_g or 0
                by_cat = self._stats.by_category_g
                by_cat[updated.category] = by_cat.get(updated.category, 0) + (updated.collected_weight_g or 0)
            self._flush()
            return updated, event

    def stats(self) -> Stats:
        with self._lock:
            return self._stats.model_copy(deep=True)
