"""AWS Lambda entry point (API Gateway HTTP API, payload format 2.0)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .bootstrap import build
from .config import get_settings
from .http import App, Request


@lru_cache(maxsize=1)
def _app() -> App:
    # Built lazily once per execution environment, so cold-start work (SSM read, client setup)
    # is amortised across invocations.
    app, _ = build(get_settings())
    return app


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    return _app().handle(Request.from_apigw(event)).to_apigw()
