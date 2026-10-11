import json
import unittest

from eloop.classifier import ClassifierChain, Prediction
from eloop.handler import lambda_handler  # noqa: F401  (import check: handler module loads)
from eloop.http import Request
from tests.helpers import (
    StubClassifier,
    auth_headers,
    call,
    make_app,
    pickup_payload,
    upload_image,
)


class PublicApiTests(unittest.TestCase):
    def test_health_and_meta(self) -> None:
        app, *_ = make_app()
        self.assertEqual(call(app, "GET", "/health"), (200, {"status": "ok"}))
        status, body = call(app, "GET", "/meta")
        self.assertEqual(status, 200)
        self.assertIn("smartphone", [c["key"] for c in body["categories"]])
        self.assertTrue(body["areas"])

    def test_unknown_route_and_wrong_method(self) -> None:
        app, *_ = make_app()
        self.assertEqual(call(app, "GET", "/nope")[0], 404)
        self.assertEqual(call(app, "DELETE", "/pickups/EL-AAAAAAAA")[0], 405)

    def test_validation_errors_are_structured(self) -> None:
        app, *_ = make_app()
        status, body = call(app, "POST", "/pickups", pickup_payload(phone="123", quantity=0))
        self.assertEqual(status, 422)
        fields = {d["field"] for d in body["error"]["details"]}
        self.assertEqual(fields, {"phone", "quantity"})

    def test_extra_fields_are_rejected(self) -> None:
        app, *_ = make_app()
        status, _ = call(app, "POST", "/pickups", pickup_payload(role="admin"))
        self.assertEqual(status, 422)

    def test_invalid_json_is_400(self) -> None:
        app, *_ = make_app()
        response = app.handle(Request(method="POST", path="/pickups", body=b"{not json"))
        self.assertEqual(response.status, 400)

    def test_unknown_category_and_out_of_range(self) -> None:
        app, *_ = make_app()
        self.assertEqual(call(app, "POST", "/pickups", pickup_payload(category="spaceship"))[1]["error"]["code"], "UNKNOWN_CATEGORY")
        far = pickup_payload(lat=19.07, lng=72.87)  # Mumbai
        self.assertEqual(call(app, "POST", "/pickups", far)[1]["error"]["code"], "NO_COLLECTOR_IN_RANGE")

    def test_upload_then_classify(self) -> None:
        classifier = ClassifierChain([StubClassifier([Prediction("laptop", 0.93, "stub")])], 0.6)
        app, _, storage, _ = make_app(classifier=classifier)
        status, ticket = call(app, "POST", "/uploads", {"content_type": "image/jpeg"})
        self.assertEqual(status, 200)
        self.assertEqual(call(app, "POST", "/classify", {"image_key": ticket["key"]})[0], 422)  # not uploaded yet
        storage.save(ticket["key"], b"jpeg")
        status, body = call(app, "POST", "/classify", {"image_key": ticket["key"]})
        self.assertEqual(status, 200)
        self.assertEqual(body["predictions"][0], {"category": "laptop", "confidence": 0.93})

    def test_upload_rejects_unsupported_content_type(self) -> None:
        app, *_ = make_app()
        self.assertEqual(call(app, "POST", "/uploads", {"content_type": "application/pdf"})[0], 422)

    def test_classify_rejects_foreign_keys(self) -> None:
        app, *_ = make_app()
        self.assertEqual(call(app, "POST", "/classify", {"image_key": "../../etc/passwd"})[0], 422)

    def test_lambda_handler_event_shape(self) -> None:
        # The API Gateway adapter is exercised without building the AWS wiring.
        request = Request.from_apigw(
            {
                "rawPath": "/health",
                "headers": {"Authorization": "Bearer x"},
                "requestContext": {"http": {"method": "get"}, "requestId": "abc"},
            }
        )
        self.assertEqual((request.method, request.path, request.request_id), ("GET", "/health", "abc"))
        self.assertEqual(request.headers["authorization"], "Bearer x")
        staged = Request.from_apigw(
            {"rawPath": "/dev/pickups/EL-1", "requestContext": {"stage": "dev", "http": {"method": "GET"}}}
        )
        self.assertEqual(staged.path, "/pickups/EL-1")
        out = make_app()[0].handle(request).to_apigw()
        self.assertEqual(out["statusCode"], 200)
        self.assertEqual(json.loads(out["body"]), {"status": "ok"})
        self.assertEqual(out["headers"]["cache-control"], "no-store")


class PickupLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.service, self.storage, self.notifier = make_app()

    def create(self, **overrides: object) -> dict:
        status, body = call(self.app, "POST", "/pickups", pickup_payload(**overrides))
        self.assertEqual(status, 201, body)
        return body

    def test_full_flow(self) -> None:
        image_key = upload_image(self.storage)
        created = self.create(image_key=image_key)
        pickup_id = created["id"]
        self.assertRegex(pickup_id, r"^EL-[0-9A-HJKMNP-TV-Z]{8}$")
        self.assertEqual(created["status"], "requested")
        self.assertEqual(created["collector"]["area"], "Dwarka")
        self.assertEqual(created["est_weight_g"], 360)  # 2 x 180 g
        self.assertEqual(self.notifier.sent[0]["collector_id"], "demo-dwarka")

        # public view never leaks personal data
        public = json.dumps(call(self.app, "GET", f"/pickups/{pickup_id}")[1])
        for secret in ("Asha", "9876543210", "Flat 12"):
            self.assertNotIn(secret, public)

        headers = auth_headers("demo-dwarka")
        _, queue = call(self.app, "GET", "/collector/pickups", headers=headers)
        entry = queue["pickups"][0]
        self.assertEqual((entry["id"], entry["contact"]), (pickup_id, None))  # PII hidden until accepted

        status, confirmed = call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["contact"]["phone"], "9876543210")

        status, collected = call(self.app, "POST", f"/collector/pickups/{pickup_id}/collect", {"weight_g": 410}, headers)
        self.assertEqual((status, collected["status"], collected["collected_weight_g"]), (200, "collected", 410))

        _, tracked = call(self.app, "GET", f"/pickups/{pickup_id}")
        self.assertTrue(tracked["chain_verified"])
        self.assertEqual([e["type"] for e in tracked["events"]], ["requested", "confirmed", "collected"])

        _, impact = call(self.app, "GET", "/impact")
        self.assertEqual((impact["pickups_total"], impact["pickups_collected"], impact["collected_g"]), (1, 1, 410))
        self.assertEqual(impact["by_category"][0]["category"], "smartphone")

    def test_collect_requires_confirmation_first(self) -> None:
        pickup_id = self.create()["id"]
        status, body = call(self.app, "POST", f"/collector/pickups/{pickup_id}/collect", {"weight_g": 100}, auth_headers("demo-dwarka"))
        self.assertEqual((status, body["error"]["code"]), (409, "CONFLICT"))

    def test_double_confirm_conflicts(self) -> None:
        pickup_id = self.create()["id"]
        headers = auth_headers("demo-dwarka")
        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=headers)[0], 200)
        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=headers)[0], 409)

    def test_auth_required_and_scoped_to_owner(self) -> None:
        pickup_id = self.create()["id"]
        self.assertEqual(call(self.app, "GET", "/collector/pickups")[0], 401)
        bad = {"authorization": "Bearer demo-dwarka:wrongkey"}
        self.assertEqual(call(self.app, "GET", "/collector/pickups", headers=bad)[0], 401)
        # a different valid collector cannot see or act on this pickup (404, not 403)
        other = auth_headers("demo-saket")
        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=other)[0], 404)
        self.assertEqual(call(self.app, "GET", "/collector/pickups", headers=other)[1], {"pickups": []})

    def test_track_unknown_id_is_404(self) -> None:
        self.assertEqual(call(self.app, "GET", "/pickups/EL-ZZZZZZZZ")[0], 404)

    def test_collect_weight_validation(self) -> None:
        pickup_id = self.create()["id"]
        headers = auth_headers("demo-dwarka")
        call(self.app, "POST", f"/collector/pickups/{pickup_id}/confirm", headers=headers)
        self.assertEqual(call(self.app, "POST", f"/collector/pickups/{pickup_id}/collect", {"weight_g": 0}, headers)[0], 422)

    def test_missing_image_is_rejected(self) -> None:
        key = "uploads/2026/10/" + "b" * 32 + ".jpg"
        status, body = call(self.app, "POST", "/pickups", pickup_payload(image_key=key))
        self.assertEqual((status, body["error"]["code"]), (422, "IMAGE_NOT_FOUND"))


if __name__ == "__main__":
    unittest.main()


class CognitoAuthTests(unittest.TestCase):
    """AUTH_MODE=cognito trusts only claims the API Gateway JWT authorizer verified."""

    def _app(self):
        app, service, storage, notifier = make_app()
        service._auth_mode = "cognito"
        return app, service

    def _get(self, app, path, claims=None, headers=None):
        response = app.handle(Request(method="GET", path=path, headers=headers or {}, claims=claims or {}))
        return response.status, response.body

    def test_verified_claims_map_to_collector(self) -> None:
        app, _ = self._app()
        status, body = self._get(app, "/collector/me", {"cognito:username": "demo-dwarka", "token_use": "id"})
        self.assertEqual(status, 200)
        self.assertEqual(body["id"], "demo-dwarka")

    def test_username_is_case_insensitive(self) -> None:
        app, _ = self._app()
        self.assertEqual(self._get(app, "/collector/me", {"cognito:username": "Demo-Dwarka"})[0], 200)

    def test_no_claims_is_unauthorized_even_with_a_valid_shared_key(self) -> None:
        app, _ = self._app()
        status, _ = self._get(app, "/collector/me", headers=auth_headers("demo-dwarka"))
        self.assertEqual(status, 401)

    def test_unknown_user_and_access_tokens_are_rejected(self) -> None:
        app, _ = self._app()
        self.assertEqual(self._get(app, "/collector/me", {"cognito:username": "stranger"})[0], 401)
        self.assertEqual(
            self._get(app, "/collector/me", {"cognito:username": "demo-dwarka", "token_use": "access"})[0], 401
        )

    def test_apigw_event_carries_authorizer_claims(self) -> None:
        event = {
            "rawPath": "/collector/me",
            "requestContext": {
                "http": {"method": "GET"},
                "authorizer": {"jwt": {"claims": {"cognito:username": "demo-rohini"}}},
            },
        }
        self.assertEqual(Request.from_apigw(event).claims, {"cognito:username": "demo-rohini"})
        self.assertEqual(Request.from_apigw({"rawPath": "/health", "requestContext": {}}).claims, {})
