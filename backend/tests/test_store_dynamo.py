"""DynamoDB store contract tests, run against moto (an in-process DynamoDB).

Skipped automatically when moto/boto3 are not installed: `pip install -r requirements-dev.txt`.
"""

import json
import os
import unittest

try:
    import boto3
    from moto import mock_aws

    HAVE_MOTO = True
except ImportError:  # pragma: no cover
    HAVE_MOTO = False

from eloop.errors import StateConflictError
from tests.helpers import auth_headers, call, make_app, pickup_payload

TABLE = "eloop-test"


def create_table(resource) -> None:
    resource.create_table(
        TableName=TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


@unittest.skipUnless(HAVE_MOTO, "moto/boto3 not installed")
class DynamoStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.update(AWS_ACCESS_KEY_ID="x", AWS_SECRET_ACCESS_KEY="x", AWS_DEFAULT_REGION="ap-south-1")
        self.mock = mock_aws()
        self.mock.start()
        resource = boto3.resource("dynamodb")
        create_table(resource)

        from eloop.store_dynamo import DynamoStore

        self.store = DynamoStore(resource.meta.client, TABLE, retention_days=180)
        self.app, self.service, self.storage, _ = make_app(store=self.store)

    def tearDown(self) -> None:
        self.mock.stop()

    def test_full_flow_matches_memory_store_behaviour(self) -> None:
        status, created = call(self.app, "POST", "/pickups", pickup_payload())
        self.assertEqual(status, 201, created)
        pickup_id = created["id"]
        headers = auth_headers("demo-dwarka")

        _, queue = call(self.app, "GET", "/collector/pickups", headers=headers)
        self.assertEqual([p["id"] for p in queue["pickups"]], [pickup_id])

        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=headers)[0], 200)
        # confirmed pickups move out of the "requested" GSI partition
        self.assertEqual(self.store.list_by_status("requested"), [])
        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/collect", {"weight_g": 395}, headers)[0], 200)

        _, tracked = call(self.app, "GET", f"/pickups/{pickup_id}")
        self.assertTrue(tracked["chain_verified"])  # hash chain survives the Decimal round trip
        self.assertEqual(len(tracked["events"]), 3)

        _, impact = call(self.app, "GET", "/impact")
        self.assertEqual((impact["pickups_total"], impact["pickups_collected"], impact["collected_g"]), (1, 1, 395))
        self.assertEqual(impact["by_category"][0], {"category": "smartphone", "label": "Smartphone", "grams": 395})

    def test_stored_item_has_ttl_and_no_floats(self) -> None:
        _, created = call(self.app, "POST", "/pickups", pickup_payload())
        item = boto3.resource("dynamodb").Table(TABLE).get_item(Key={"PK": f"PICKUP#{created['id']}", "SK": "META"})["Item"]
        self.assertIn("ttl", item)
        self.assertEqual(item["GSI1PK"], "STATUS#requested")
        json.dumps(item, default=str)  # serialisable

    def test_stale_advance_is_rejected(self) -> None:
        _, created = call(self.app, "POST", "/pickups", pickup_payload())
        kwargs = dict(
            expected_status="requested", new_status="confirmed", event_type="confirmed",
            actor="collector:demo-dwarka", data={"collector_id": "demo-dwarka"}, at="2026-10-11T06:00:00Z", changes={},
        )
        self.store.advance(created["id"], **kwargs)  # type: ignore[arg-type]
        with self.assertRaises(StateConflictError):
            self.store.advance(created["id"], **kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
