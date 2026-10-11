"""Domain models and request schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["requested", "confirmed", "collected"]
ClassifiedBy = Literal["rekognition", "bedrock", "manual"]
Scalar = str | int | bool

PHONE_PATTERN = r"^[6-9]\d{9}$"


class Collector(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    area: str
    lat: float
    lng: float
    accepts: tuple[str, ...]  # category keys, or ("*",) for everything
    demo: bool = False

    def accepts_category(self, category: str) -> bool:
        return "*" in self.accepts or category in self.accepts


class Area(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    lat: float
    lng: float


class Event(BaseModel):
    """One entry in a pickup's hash-chained history. `data` holds scalars only (no floats)."""

    model_config = ConfigDict(frozen=True)

    seq: int
    type: str
    at: str
    actor: str
    data: dict[str, Scalar]
    prev_hash: str
    hash: str


class Pickup(BaseModel):
    id: str
    status: Status
    category: str
    quantity: int
    classified_by: ClassifiedBy
    confidence: float | None = None
    image_key: str | None = None
    est_weight_g: int
    value_inr_min: int
    value_inr_max: int
    contact_name: str
    contact_phone: str
    address: str
    lat: float
    lng: float
    area: str | None = None
    collector_id: str
    distance_km: float
    created_at: str
    updated_at: str
    collected_weight_g: int | None = None
    version: int = 1


class Stats(BaseModel):
    pickups_total: int = 0
    pickups_collected: int = 0
    collected_g: int = 0
    by_category_g: dict[str, int] = Field(default_factory=dict)


# ---- Request schemas ---------------------------------------------------------------------------


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UploadRequest(_Request):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class ClassifyRequest(_Request):
    image_key: str = Field(max_length=200)


class PickupRequest(_Request):
    category: str = Field(max_length=40)
    quantity: int = Field(default=1, ge=1, le=20)
    image_key: str | None = Field(default=None, max_length=200)
    classified_by: ClassifiedBy = "manual"
    confidence: float | None = Field(default=None, ge=0, le=1)
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=PHONE_PATTERN)
    address: str = Field(min_length=10, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    area: str | None = Field(default=None, max_length=60)


class CollectRequest(_Request):
    weight_g: int = Field(ge=1, le=200_000)
