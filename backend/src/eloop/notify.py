"""Collector notifications. Messages never include personal data."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def new_pickup(self, *, pickup_id: str, collector_id: str, category: str, area: str) -> None: ...


class LogNotifier:
    def new_pickup(self, *, pickup_id: str, collector_id: str, category: str, area: str) -> None:
        log.info("new pickup %s for %s (%s, %s)", pickup_id, collector_id, category, area)


class SnsNotifier:
    def __init__(self, client: Any, topic_arn: str) -> None:
        self._client = client
        self._topic_arn = topic_arn

    def new_pickup(self, *, pickup_id: str, collector_id: str, category: str, area: str) -> None:
        message = {"pickup_id": pickup_id, "collector_id": collector_id, "category": category, "area": area}
        try:
            self._client.publish(
                TopicArn=self._topic_arn,
                Subject="New e-waste pickup request",
                Message=json.dumps(message),
                MessageAttributes={"collector_id": {"DataType": "String", "StringValue": collector_id}},
            )
        except Exception:  # noqa: BLE001 - a notification failure must not fail the request
            log.warning("sns publish failed for %s", pickup_id, exc_info=True)
