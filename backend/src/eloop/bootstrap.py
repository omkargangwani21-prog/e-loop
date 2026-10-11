"""Dependency wiring. The only module that knows which concrete adapters run where."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .classifier import BedrockClassifier, Classifier, ClassifierChain, RekognitionClassifier
from .config import Settings
from .http import App
from .notify import LogNotifier, Notifier, SnsNotifier
from .routes import build_app
from .service import Limits, PickupService, load_areas, load_collectors
from .storage import LocalStorage, S3Storage, Storage
from .store import MemoryStore, Store


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:  # Lambda pre-installs a handler; locally we add one
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.setFormatter(_JsonFormatter())


def build_service(settings: Settings) -> PickupService:
    collectors = load_collectors()
    classifiers: list[Classifier] = []

    store: Store
    storage: Storage
    notifier: Notifier

    if settings.mode == "aws":
        import boto3
        from botocore.config import Config

        s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
        storage = S3Storage(s3, settings.bucket_name, settings.max_upload_bytes)

        from .store_dynamo import DynamoStore

        store = DynamoStore(boto3.resource("dynamodb").meta.client, settings.table_name, settings.retention_days)
        notifier = SnsNotifier(boto3.client("sns"), settings.topic_arn) if settings.topic_arn else LogNotifier()
        secret = ""  # only needed for the shared-key fallback; Cognito mode never reads it
        if settings.auth_mode != "cognito":
            secret = boto3.client("ssm").get_parameter(Name=settings.collector_secret_param, WithDecryption=True)[
                "Parameter"
            ]["Value"]

        for name in settings.classifier_chain:
            if name == "rekognition":
                classifiers.append(RekognitionClassifier(boto3.client("rekognition"), settings.bucket_name))
            elif name == "bedrock" and settings.bedrock_model_id:
                classifiers.append(
                    BedrockClassifier(boto3.client("bedrock-runtime"), storage, settings.bedrock_model_id)
                )
    else:
        data_dir = Path(settings.local_data_dir)
        storage = LocalStorage(data_dir, settings.max_upload_bytes)  # keys already start with "uploads/"
        store = MemoryStore(data_dir / "db.json")
        notifier = LogNotifier()
        secret = settings.collector_secret

    return PickupService(
        store=store,
        storage=storage,
        classifier=ClassifierChain(classifiers, settings.min_confidence),
        notifier=notifier,
        collectors=collectors,
        areas=load_areas(),
        collector_secret=secret,
        limits=Limits(settings.max_upload_bytes, settings.max_match_km),
        auth_mode=settings.auth_mode,
    )


def build(settings: Settings) -> tuple[App, PickupService]:
    configure_logging(settings.log_level)
    service = build_service(settings)
    return build_app(service), service
