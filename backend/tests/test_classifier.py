import unittest

from eloop.classifier import (
    BedrockClassifier,
    ClassifierChain,
    Prediction,
    RekognitionClassifier,
)
from eloop.storage import LocalStorage, new_key
from tests.helpers import StubClassifier


class FakeRekognition:
    def __init__(self, labels: list[dict]) -> None:
        self._labels = labels
        self.calls: list[dict] = []

    def detect_labels(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"Labels": self._labels}


class FakeBedrock:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict] = []

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": self._text}]}}}


class RaisingClassifier:
    name = "raising"

    def classify(self, image_key: str) -> list[Prediction]:
        raise RuntimeError("AccessDeniedException: account is being verified")


class RekognitionTests(unittest.TestCase):
    def test_maps_labels_and_keeps_best_confidence_per_category(self) -> None:
        client = FakeRekognition(
            [
                {"Name": "Mobile Phone", "Confidence": 97.2},
                {"Name": "Phone", "Confidence": 88.0},
                {"Name": "Electronics", "Confidence": 99.0},  # generic, must be ignored
                {"Name": "Cable", "Confidence": 71.5, "Aliases": [{"Name": "Wire"}]},
            ]
        )
        result = RekognitionClassifier(client, "bucket").classify("uploads/2026/10/" + "a" * 32 + ".jpg")
        self.assertEqual([p.category for p in result], ["smartphone", "charger_cable"])
        self.assertAlmostEqual(result[0].confidence, 0.972, places=3)
        self.assertEqual(client.calls[0]["Image"]["S3Object"]["Bucket"], "bucket")

    def test_no_known_labels_returns_empty(self) -> None:
        client = FakeRekognition([{"Name": "Tree", "Confidence": 99.0}])
        self.assertEqual(RekognitionClassifier(client, "b").classify("k"), [])


class BedrockTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.storage = LocalStorage(tempfile.mkdtemp(), 1_000_000)
        self.key = new_key("image/jpeg")
        self.storage.save(self.key, b"bytes")

    def classify(self, text: str) -> list[Prediction]:
        client = FakeBedrock(text)
        result = BedrockClassifier(client, self.storage, "apac.model").classify(self.key)
        call = client.calls[0]
        self.assertEqual(call["modelId"], "apac.model")
        self.assertEqual(call["messages"][0]["content"][0]["image"]["format"], "jpeg")
        return result

    def test_parses_clean_json(self) -> None:
        result = self.classify('{"category": "laptop", "confidence": 0.91}')
        self.assertEqual((result[0].category, result[0].confidence), ("laptop", 0.91))

    def test_parses_json_wrapped_in_prose(self) -> None:
        result = self.classify('Sure! {"category": "tablet", "confidence": 0.7} Hope that helps.')
        self.assertEqual(result[0].category, "tablet")

    def test_rejects_unknown_category(self) -> None:
        self.assertEqual(self.classify('{"category": "spaceship", "confidence": 0.9}'), [])

    def test_rejects_garbage(self) -> None:
        self.assertEqual(self.classify("I cannot help with that"), [])

    def test_clamps_confidence(self) -> None:
        self.assertEqual(self.classify('{"category": "laptop", "confidence": 7}')[0].confidence, 1.0)


class ChainTests(unittest.TestCase):
    def test_skips_failing_classifier_and_uses_next(self) -> None:
        good = StubClassifier([Prediction("laptop", 0.9, "stub")])
        with self.assertLogs("eloop.classifier", level="WARNING"):
            result = ClassifierChain([RaisingClassifier(), good], 0.6).classify("k")  # type: ignore[list-item]
        self.assertEqual((result.source, result.predictions[0].category), ("stub", "laptop"))

    def test_low_confidence_falls_through_to_manual(self) -> None:
        weak = StubClassifier([Prediction("laptop", 0.3, "stub")])
        result = ClassifierChain([weak], 0.6).classify("k")  # type: ignore[list-item]
        self.assertEqual((result.source, result.predictions), ("manual", []))

    def test_empty_chain_is_manual(self) -> None:
        self.assertEqual(ClassifierChain([], 0.6).classify("k").source, "manual")


if __name__ == "__main__":
    unittest.main()
