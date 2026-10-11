"""Route table: translates HTTP requests into service calls."""

from __future__ import annotations

from .http import App, Request, Response, Router
from .models import ClassifyRequest, CollectRequest, PickupRequest, UploadRequest
from .service import PickupService


def build_app(service: PickupService) -> App:
    router = Router()

    def health(_: Request) -> Response:
        return Response(200, {"status": "ok"})

    router.add("GET", "/health", health)
    router.add("GET", "/meta", lambda _: Response(200, service.meta()))
    router.add("POST", "/uploads", lambda r: Response(200, service.start_upload(r.parse(UploadRequest))))
    router.add("POST", "/classify", lambda r: Response(200, service.classify(r.parse(ClassifyRequest))))
    router.add("POST", "/pickups", lambda r: Response(201, service.create_pickup(r.parse(PickupRequest))))
    router.add("GET", "/pickups/{pickup_id}", lambda r: Response(200, service.track(r.path_params["pickup_id"])))
    router.add("GET", "/impact", lambda _: Response(200, service.impact()))

    def me(r: Request) -> Response:
        return Response(200, service.collector_profile(service.authenticate(r.headers, r.claims)))

    def queue(r: Request) -> Response:
        return Response(200, service.collector_queue(service.authenticate(r.headers, r.claims)))

    def confirm(r: Request) -> Response:
        collector = service.authenticate(r.headers, r.claims)
        return Response(200, service.confirm(collector, r.path_params["pickup_id"]))

    def collect(r: Request) -> Response:
        collector = service.authenticate(r.headers, r.claims)
        body = r.parse(CollectRequest)
        return Response(200, service.collect(collector, r.path_params["pickup_id"], body))

    router.add("GET", "/collector/me", me)
    router.add("GET", "/collector/pickups", queue)
    router.add("POST", "/collector/pickups/{pickup_id}/confirm", confirm)
    router.add("POST", "/collector/pickups/{pickup_id}/collect", collect)

    return App(router)
