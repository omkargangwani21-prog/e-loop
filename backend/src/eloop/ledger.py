"""Tamper-evident, append-only event chain for pickups.

Every event stores the hash of its predecessor, so altering or removing any past event breaks
verification of everything after it. This is a plain SHA-256 hash chain, not a blockchain: its
purpose is to give producers and auditors a cheap integrity check on collection records.

Event `data` must contain only str, int or bool values. Floats are rejected so the canonical
encoding is identical before and after a round trip through DynamoDB (which returns Decimals).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from .models import Event, Scalar

GENESIS_HASH = "0" * 64


def _canonical(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def compute_hash(
    prev_hash: str, seq: int, type_: str, at: str, actor: str, data: Mapping[str, Scalar]
) -> str:
    body = {"seq": seq, "type": type_, "at": at, "actor": actor, "data": dict(data)}
    return hashlib.sha256(prev_hash.encode() + b"|" + _canonical(body)).hexdigest()


def build_event(
    prev: Event | None, *, type_: str, actor: str, data: Mapping[str, Scalar], at: str
) -> Event:
    for key, value in data.items():
        if isinstance(value, float):
            raise TypeError(f"event data '{key}' must not be a float; use integer units")
    seq = 1 if prev is None else prev.seq + 1
    prev_hash = GENESIS_HASH if prev is None else prev.hash
    return Event(
        seq=seq,
        type=type_,
        at=at,
        actor=actor,
        data=dict(data),
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, seq, type_, at, actor, data),
    )


def verify_chain(events: Sequence[Event]) -> bool:
    expected_prev = GENESIS_HASH
    for index, event in enumerate(sorted(events, key=lambda e: e.seq), start=1):
        if event.seq != index or event.prev_hash != expected_prev:
            return False
        recomputed = compute_hash(
            event.prev_hash, event.seq, event.type, event.at, event.actor, event.data
        )
        if recomputed != event.hash:
            return False
        expected_prev = event.hash
    return True
