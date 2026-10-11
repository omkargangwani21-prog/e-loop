"""DynamoDB single-table store.

Key design (one table, one GSI):

    PK                  SK            Contents
    PICKUP#<id>         META          The pickup. GSI1PK=STATUS#<status>, GSI1SK=<created>#<id>.
    PICKUP#<id>         EVT#000001..  Append-only ledger events (hash chained).
    STATS               GLOBAL        Atomic counters for the public impact page.

Every state change is one TransactWriteItems: the META update is conditional on the expected
version and status, the event is a conditional insert, and counters are incremented atomically.
Two collectors racing for the same pickup therefore cannot both win.

`client` is a boto3 *resource* client (`boto3.resource("dynamodb").meta.client`), which accepts
plain Python values. Floats are converted to Decimal on write and back on read.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from .errors import PickupNotFoundError, StateConflictError
from .ledger import build_event
from .models import Event, Pickup, Scalar, Stats, Status

_KEY_ATTRS = {"PK", "SK", "GSI1PK", "GSI1SK", "ttl"}


def _to_dynamo(value: Any) -> Any:
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def _is_condition_failure(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    if code == "ConditionalCheckFailedException":
        return True
    if code == "TransactionCanceledException":
        reasons = error.response.get("CancellationReasons", [])
        return any(r.get("Code") == "ConditionalCheckFailed" for r in reasons)
    return False


class DynamoStore:
    def __init__(self, client: Any, table_name: str, retention_days: int = 180) -> None:
        self._client = client
        self._table = table_name
        self._retention_s = retention_days * 86_400

    # -- item shaping ----------------------------------------------------------------------

    def _meta_item(self, pickup: Pickup) -> dict[str, Any]:
        created = datetime.fromisoformat(pickup.created_at.replace("Z", "+00:00"))
        item = _to_dynamo(pickup.model_dump(mode="json", exclude_none=True))
        item.update(
            PK=f"PICKUP#{pickup.id}",
            SK="META",
            GSI1PK=f"STATUS#{pickup.status}",
            GSI1SK=f"{pickup.created_at}#{pickup.id}",
            ttl=int(created.timestamp()) + self._retention_s,  # personal data expires with the META item
        )
        return item

    @staticmethod
    def _event_item(pickup_id: str, event: Event) -> dict[str, Any]:
        item = _to_dynamo(event.model_dump(mode="json"))
        item.update(PK=f"PICKUP#{pickup_id}", SK=f"EVT#{event.seq:06d}")
        return item

    @staticmethod
    def _pickup_from_item(item: Mapping[str, Any]) -> Pickup:
        clean = {k: v for k, v in item.items() if k not in _KEY_ATTRS}
        return Pickup.model_validate(_from_dynamo(clean))

    # -- Store ---------------------------------------------------------------------------------

    def create(self, pickup: Pickup, event: Event) -> None:
        try:
            self._client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self._table,
                            "Item": self._meta_item(pickup),
                            "ConditionExpression": "attribute_not_exists(PK)",
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._table,
                            "Item": self._event_item(pickup.id, event),
                            "ConditionExpression": "attribute_not_exists(PK)",
                        }
                    },
                    {
                        "Update": {
                            "TableName": self._table,
                            "Key": {"PK": "STATS", "SK": "GLOBAL"},
                            "UpdateExpression": "ADD pickups_total :one",
                            "ExpressionAttributeValues": {":one": 1},
                        }
                    },
                ]
            )
        except ClientError as exc:
            if _is_condition_failure(exc):
                raise StateConflictError("pickup id already exists") from exc
            raise

    def get(self, pickup_id: str) -> Pickup | None:
        response = self._client.get_item(
            TableName=self._table, Key={"PK": f"PICKUP#{pickup_id}", "SK": "META"}, ConsistentRead=True
        )
        item = response.get("Item")
        return self._pickup_from_item(item) if item else None

    def events(self, pickup_id: str) -> list[Event]:
        response = self._client.query(
            TableName=self._table,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": f"PICKUP#{pickup_id}", ":prefix": "EVT#"},
            ConsistentRead=True,
        )
        return [
            Event.model_validate({k: _from_dynamo(v) for k, v in item.items() if k not in _KEY_ATTRS})
            for item in response.get("Items", [])
        ]

    def list_by_status(self, status: Status, limit: int = 100) -> list[Pickup]:
        response = self._client.query(
            TableName=self._table,
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": f"STATUS#{status}"},
            ScanIndexForward=True,
            Limit=limit,
        )
        return [self._pickup_from_item(item) for item in response.get("Items", [])]

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
        pickup = self.get(pickup_id)
        if pickup is None:
            raise PickupNotFoundError(pickup_id)
        if pickup.status != expected_status:
            raise StateConflictError(f"pickup is {pickup.status}, expected {expected_status}")

        history = self.events(pickup_id)
        event = build_event(history[-1] if history else None, type_=event_type, actor=actor, data=data, at=at)
        updated = pickup.model_copy(
            update={**changes, "status": new_status, "updated_at": at, "version": pickup.version + 1}
        )

        items: list[dict[str, Any]] = [
            {
                "Put": {
                    "TableName": self._table,
                    "Item": self._meta_item(updated),
                    "ConditionExpression": "#v = :v AND #s = :expected",
                    "ExpressionAttributeNames": {"#v": "version", "#s": "status"},
                    "ExpressionAttributeValues": {":v": pickup.version, ":expected": expected_status},
                }
            },
            {
                "Put": {
                    "TableName": self._table,
                    "Item": self._event_item(pickup_id, event),
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
        ]
        if new_status == "collected":
            weight = updated.collected_weight_g or 0
            items.append(
                {
                    "Update": {
                        "TableName": self._table,
                        "Key": {"PK": "STATS", "SK": "GLOBAL"},
                        "UpdateExpression": "ADD pickups_collected :one, collected_g :w, #cat :w",
                        "ExpressionAttributeNames": {"#cat": f"cat_{updated.category}"},
                        "ExpressionAttributeValues": {":one": 1, ":w": weight},
                    }
                }
            )
        try:
            self._client.transact_write_items(TransactItems=items)
        except ClientError as exc:
            if _is_condition_failure(exc):
                raise StateConflictError("pickup was modified concurrently") from exc
            raise
        return updated, event

    def stats(self) -> Stats:
        response = self._client.get_item(
            TableName=self._table, Key={"PK": "STATS", "SK": "GLOBAL"}, ConsistentRead=True
        )
        item = _from_dynamo(response.get("Item", {}))
        by_category = {k.removeprefix("cat_"): int(v) for k, v in item.items() if k.startswith("cat_")}
        return Stats(
            pickups_total=int(item.get("pickups_total", 0)),
            pickups_collected=int(item.get("pickups_collected", 0)),
            collected_g=int(item.get("collected_g", 0)),
            by_category_g=by_category,
        )
