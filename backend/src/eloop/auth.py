"""Collector authentication.

Two modes, chosen by AUTH_MODE:

* ``cognito`` (AWS): an Amazon Cognito user pool issues the ID token and the API Gateway JWT authorizer
  verifies signature, issuer, audience and expiry before Lambda runs. The Cognito username *is* the
  collection point ID, so this module only maps verified claims to a known collector.
* ``hmac`` (local dev and tests): key = HMAC-SHA256(secret, collector_id), so no per-collector secrets
  are stored.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping

from .errors import ApiError
from .models import Collector


def derive_key(secret: str, collector_id: str) -> str:
    return hmac.new(secret.encode(), collector_id.encode(), hashlib.sha256).hexdigest()[:32]


def authenticate(
    headers: Mapping[str, str], secret: str, collectors: Mapping[str, Collector]
) -> Collector:
    scheme, _, credentials = headers.get("authorization", "").partition(" ")
    collector_id, _, supplied = credentials.partition(":")
    collector = collectors.get(collector_id)
    if scheme.lower() != "bearer" or collector is None:
        raise ApiError.unauthorized()
    if not hmac.compare_digest(supplied, derive_key(secret, collector_id)):
        raise ApiError.unauthorized()
    return collector


def authenticate_claims(claims: Mapping[str, str], collectors: Mapping[str, Collector]) -> Collector:
    """Map claims verified upstream by the API Gateway JWT authorizer to a collection point."""
    if claims.get("token_use", "id") != "id":
        raise ApiError.unauthorized()
    collector = collectors.get(claims.get("cognito:username", "").strip().lower())
    if collector is None:
        raise ApiError.unauthorized()  # valid Cognito user, but not a registered collection point
    return collector
