"""Image classification behind one interface so the backing model is swappable.

Order of preference is configured with CLASSIFIER_CHAIN (e.g. "rekognition,bedrock"). Any
classifier that raises or returns nothing above the confidence floor is skipped, and when the
whole chain comes up empty the user simply picks the category by hand. The product therefore
works even when an AI service is throttled, gated or down.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .catalog import BY_KEY, LABEL_INDEX
from .storage import Storage, image_format

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Prediction:
    category: str
    confidence: float  # 0..1
    source: str


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    predictions: list[Prediction]
    source: str  # "rekognition" | "bedrock" | "manual"


class Classifier(Protocol):
    name: str

    def classify(self, image_key: str) -> list[Prediction]: ...


class RekognitionClassifier:
    """Maps Amazon Rekognition DetectLabels output onto our own category catalog."""

    name = "rekognition"

    def __init__(self, client: Any, bucket: str, min_confidence_pct: float = 60.0) -> None:
        self._client = client
        self._bucket = bucket
        self._min_confidence_pct = min_confidence_pct

    def classify(self, image_key: str) -> list[Prediction]:
        response = self._client.detect_labels(
            Image={"S3Object": {"Bucket": self._bucket, "Name": image_key}},
            MaxLabels=30,
            MinConfidence=self._min_confidence_pct,
        )
        best: dict[str, float] = {}
        for label in response.get("Labels", []):
            names = [label.get("Name", "")]
            names.extend(alias.get("Name", "") for alias in label.get("Aliases", []))
            confidence = float(label.get("Confidence", 0.0)) / 100.0
            for name in names:
                category = LABEL_INDEX.get(name.strip().lower())
                if category is not None and confidence > best.get(category, 0.0):
                    best[category] = confidence
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
        return [Prediction(category, conf, self.name) for category, conf in ranked]


_JSON_OBJECT = re.compile(r"\{.*?\}", re.DOTALL)


class BedrockClassifier:
    """Vision-capable foundation model via the Bedrock Converse API (one request shape for all)."""

    name = "bedrock"

    def __init__(self, client: Any, storage: Storage, model_id: str) -> None:
        self._client = client
        self._storage = storage
        self._model_id = model_id

    @staticmethod
    def _prompt() -> str:
        options = ", ".join(sorted(BY_KEY))
        return (
            "You identify discarded consumer electronics from a photo. "
            f"Choose exactly one category from: {options}. "
            'Reply with only JSON: {"category": "<key>", "confidence": <0 to 1>}.'
        )

    def classify(self, image_key: str) -> list[Prediction]:
        image_bytes = self._storage.read(image_key)
        response = self._client.converse(
            modelId=self._model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": {"format": image_format(image_key), "source": {"bytes": image_bytes}}},
                        {"text": self._prompt()},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 120, "temperature": 0},
        )
        text = "".join(
            block.get("text", "") for block in response["output"]["message"]["content"]
        )
        return self._parse(text)

    def _parse(self, text: str) -> list[Prediction]:
        match = _JSON_OBJECT.search(text)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
            category = str(payload["category"]).strip().lower()
            confidence = min(1.0, max(0.0, float(payload.get("confidence", 0.0))))
        except (ValueError, KeyError, TypeError):
            return []
        if category not in BY_KEY:
            return []
        return [Prediction(category, confidence, self.name)]


class ClassifierChain:
    def __init__(self, classifiers: list[Classifier], min_confidence: float) -> None:
        self._classifiers = classifiers
        self._min_confidence = min_confidence

    def classify(self, image_key: str) -> ClassificationResult:
        for classifier in self._classifiers:
            try:
                predictions = classifier.classify(image_key)
            except Exception:  # noqa: BLE001 - a failing AI provider must never block a pickup
                log.warning("classifier %s failed", classifier.name, exc_info=True)
                continue
            confident = [p for p in predictions if p.confidence >= self._min_confidence]
            if confident:
                return ClassificationResult(confident, classifier.name)
        return ClassificationResult([], "manual")
