"""Shared fixtures for tests: a fully in-memory service with a controllable clock."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from eloop.auth import derive_key
from eloop.classifier import ClassificationResult, ClassifierChain, Prediction
from eloop.http import App, Request
from eloop.notify import LogNotifier
from eloop.routes import build_app
from eloop.service import Limits, PickupService, load_areas, load_collectors
from eloop.storage import LocalStorage, new_key
from eloop.store import MemoryStore

SECRET = "test-secret"


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 10, 11, 5, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


class RecordingNotifier(LogNotifier):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def new_pickup(self, *, pickup_id: str, collector_id: str, category: str, area: str) -> None:
        self.sent.append({"pickup_id": pickup_id, "collector_id": collector_id, "category": category, "area": area})


class StubClassifier:
    name = "stub"

    def __init__(self, predictions: list[Prediction] | None = None) -> None:
        self._predictions = predictions or []

    def classify(self, image_key: str) -> list[Prediction]:
        return self._predictions


def make_service(
    store: object | None = None,
    classifier: ClassifierChain | None = None,
    id_factory: Callable[[], str] | None = None,
) -> tuple[PickupService, LocalStorage, RecordingNotifier]:
    tmp = Path(tempfile.mkdtemp(prefix="eloop-test-"))
    storage = LocalStorage(tmp, 3_500_000)
    notifier = RecordingNotifier()
    kwargs = {"id_factory": id_factory} if id_factory else {}
    service = PickupService(
        store=store or MemoryStore(),  # type: ignore[arg-type]
        storage=storage,
        classifier=classifier or ClassifierChain([], 0.6),
        notifier=notifier,
        collectors=load_collectors(),
        areas=load_areas(),
        collector_secret=SECRET,
        limits=Limits(3_500_000, 30.0),
        clock=FakeClock(),
        **kwargs,
    )
    return service, storage, notifier


def upload_image(storage: LocalStorage) -> str:
    key = new_key("image/jpeg")
    storage.save(key, b"\xff\xd8\xff fake jpeg bytes")
    return key


def auth_headers(collector_id: str, secret: str = SECRET) -> dict[str, str]:
    return {"authorization": f"Bearer {collector_id}:{derive_key(secret, collector_id)}"}


def pickup_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category": "smartphone",
        "quantity": 2,
        "classified_by": "manual",
        "name": "Asha Verma",
        "phone": "9876543210",
        "address": "Flat 12, Block C, Sector 10, Dwarka",
        "lat": 28.5830,
        "lng": 77.0510,
        "area": "Dwarka",
    }
    payload.update(overrides)
    return payload


def make_app(**kwargs: object) -> tuple[App, PickupService, LocalStorage, RecordingNotifier]:
    service, storage, notifier = make_service(**kwargs)  # type: ignore[arg-type]
    return build_app(service), service, storage, notifier


def call(app: App, method: str, path: str, body: object | None = None, headers: dict[str, str] | None = None):
    import json

    request = Request(
        method=method,
        path=path,
        headers=headers or {},
        body=json.dumps(body).encode() if body is not None else b"",
    )
    response = app.handle(request)
    return response.status, response.body


__all__ = [
    "SECRET",
    "ClassificationResult",
    "StubClassifier",
    "auth_headers",
    "call",
    "make_app",
    "make_service",
    "pickup_payload",
    "upload_image",
]
