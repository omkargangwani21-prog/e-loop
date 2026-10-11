"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Settings:
    mode: str = "local"  # "aws" wires DynamoDB/S3/SNS/Rekognition; "local" wires in-process fakes
    stage: str = "dev"
    table_name: str = ""
    bucket_name: str = ""
    topic_arn: str = ""
    classifier_chain: tuple[str, ...] = ("manual",)
    bedrock_model_id: str = ""
    collector_secret_param: str = ""  # SSM parameter name (aws mode)
    collector_secret: str = "dev-secret"  # local mode only
    auth_mode: str = "hmac"  # "cognito": trust claims verified by the API Gateway JWT authorizer
    local_data_dir: str = ".local"
    max_upload_bytes: int = 3_500_000
    max_match_km: float = 30.0
    min_confidence: float = 0.6
    retention_days: int = 180
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        chain = tuple(s.strip().lower() for s in e.get("CLASSIFIER_CHAIN", "manual").split(","))
        return cls(
            mode=e.get("ELOOP_MODE", "local"),
            stage=e.get("STAGE", "dev"),
            table_name=e.get("TABLE_NAME", ""),
            bucket_name=e.get("BUCKET_NAME", ""),
            topic_arn=e.get("TOPIC_ARN", ""),
            classifier_chain=tuple(s for s in chain if s),
            bedrock_model_id=e.get("BEDROCK_MODEL_ID", ""),
            collector_secret_param=e.get("COLLECTOR_SECRET_PARAM", ""),
            collector_secret=e.get("COLLECTOR_SECRET", "dev-secret"),
            auth_mode=e.get("AUTH_MODE", "hmac").strip().lower(),
            local_data_dir=e.get("LOCAL_DATA_DIR", ".local"),
            max_upload_bytes=int(e.get("MAX_UPLOAD_BYTES", "3500000")),
            max_match_km=float(e.get("MAX_MATCH_KM", "30")),
            min_confidence=float(e.get("MIN_CONFIDENCE", "0.6")),
            retention_days=int(e.get("RETENTION_DAYS", "180")),
            log_level=e.get("LOG_LEVEL", "INFO").upper(),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
