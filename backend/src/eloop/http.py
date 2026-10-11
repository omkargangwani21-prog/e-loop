"""A deliberately small HTTP layer shared by the Lambda handler and the local dev server."""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import ApiError

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 16_384
M = TypeVar("M", bound=BaseModel)

SECURITY_HEADERS = {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
}


def _jwt_claims(context: dict[str, Any]) -> dict[str, str]:
    """Claims the API Gateway JWT authorizer already verified; empty on routes without an authorizer."""
    claims = (context.get("authorizer") or {}).get("jwt", {}).get("claims") or {}
    return {str(k): str(v) for k, v in claims.items()}


@dataclass(slots=True)
class Request:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    path_params: dict[str, str] = field(default_factory=dict)
    claims: dict[str, str] = field(default_factory=dict)  # verified JWT claims (API Gateway authorizer)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def from_apigw(cls, event: dict[str, Any]) -> Request:
        """Build a request from an API Gateway HTTP API (payload format 2.0) event."""
        context = event.get("requestContext", {})
        http = context.get("http", {})
        body = event.get("body") or ""
        raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()
        path = event.get("rawPath", "/")
        stage = context.get("stage", "$default")
        if stage != "$default" and (path == f"/{stage}" or path.startswith(f"/{stage}/")):
            path = path[len(stage) + 1 :] or "/"  # named stages prefix rawPath; routes are stage-agnostic
        return cls(
            method=http.get("method", "GET").upper(),
            path=path,
            headers={k.lower(): v for k, v in (event.get("headers") or {}).items()},
            body=raw,
            claims=_jwt_claims(context),
            request_id=event.get("requestContext", {}).get("requestId") or uuid.uuid4().hex,
        )

    def parse(self, model: type[M]) -> M:
        if len(self.body) > MAX_BODY_BYTES:
            raise ApiError(413, "PAYLOAD_TOO_LARGE", "Request body is too large")
        try:
            payload = json.loads(self.body or b"{}")
        except ValueError as exc:
            raise ApiError(400, "INVALID_JSON", "Request body must be valid JSON") from exc
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            details = [
                {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
                for err in exc.errors()
            ]
            raise ApiError(422, "VALIDATION_ERROR", "Some fields are invalid", details) from exc


@dataclass(slots=True)
class Response:
    status: int = 200
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_apigw(self) -> dict[str, Any]:
        return {
            "statusCode": self.status,
            "headers": {**SECURITY_HEADERS, **self.headers},
            "body": "" if self.body is None else json.dumps(self.body),
        }


Handler = Callable[[Request], Response]


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def add(self, method: str, template: str, handler: Handler) -> None:
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template)
        self._routes.append((method.upper(), re.compile(f"^{pattern}$"), handler))

    def dispatch(self, request: Request) -> Response:
        path_matched = False
        for method, pattern, handler in self._routes:
            match = pattern.match(request.path)
            if not match:
                continue
            path_matched = True
            if method == request.method:
                request.path_params = match.groupdict()
                return handler(request)
        if path_matched:
            raise ApiError(405, "METHOD_NOT_ALLOWED", "Method not allowed")
        raise ApiError.not_found("Route")


class App:
    def __init__(self, router: Router) -> None:
        self._router = router

    def handle(self, request: Request) -> Response:
        try:
            return self._router.dispatch(request)
        except ApiError as error:
            body: dict[str, Any] = {
                "error": {"code": error.code, "message": error.message, "request_id": request.request_id}
            }
            if error.details:
                body["error"]["details"] = error.details
            return Response(error.status, body)
        except Exception:
            log.exception("unhandled error", extra={"request_id": request.request_id})
            return Response(
                500,
                {"error": {"code": "INTERNAL", "message": "Something went wrong", "request_id": request.request_id}},
            )
