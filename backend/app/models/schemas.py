from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class CitationSchema(BaseModel):
    section_number: str
    section_title: str
    relevant_text: str
    source_url: str = ""
    regulation_id: uuid.UUID | None = None


class ConstraintSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: str
    parameter: str
    rule_text: str
    value: str | None = None
    numeric_value: float | None = None
    unit: str | None = None
    confidence: float = 1.0
    source_layer: str  # "deterministic_lookup" | "computed" | "llm_interpreted"
    determination_type: str  # "deterministic" | "interpreted" | "inferred"
    citations: list[CitationSchema] = Field(default_factory=list)
    reasoning: str = ""
    geometry_geojson: dict | None = None
    zone_rule_id: uuid.UUID | None = None


class ParcelSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    apn: str
    address: str | None = None
    zone_code: str
    zone_class: str
    height_district: str | None = None
    specific_plan: str | None = None
    overlay_zones: list[str] = Field(default_factory=list)
    lot_area_sqft: float | None = None
    lot_width_ft: float | None = None
    lot_depth_ft: float | None = None
    geometry_geojson: dict | None = None
    building_footprints_geojson: list | dict | None = None
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    community_plan_area: str | None = None


class AssessmentSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parcel: ParcelSchema
    building_type: str
    project_inputs: dict | None = None
    constraints: list[ConstraintSchema] = Field(default_factory=list)
    overall_confidence: float = 1.0
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AssessmentRequest(BaseModel):
    address: str | None = None
    apn: str | None = None
    building_type: Literal["SFH", "ADU", "Guest House"] = "SFH"
    project_inputs: dict | None = None

    @model_validator(mode="after")
    def require_address_or_apn(self) -> AssessmentRequest:
        if not self.address and not self.apn:
            raise ValueError("At least one of 'address' or 'apn' must be provided")
        return self


class ChatMessageSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    role: str
    content: str
    citations: list[CitationSchema] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=5000)


class FeedbackRequest(BaseModel):
    constraint_id: uuid.UUID | None = None
    assessment_id: uuid.UUID
    rating: Literal["positive", "negative"]
    comment: str | None = None


class FeedbackSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    constraint_id: uuid.UUID | None = None
    assessment_id: uuid.UUID
    rating: str
    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ZoneRuleSchema(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    zone_class: str
    parameter: str
    category: str
    base_value: float
    unit: str
    conditions: dict | None = None
    applies_to: list[str] = Field(default_factory=lambda: ["ALL"])
    section_number: str
    source_text: str
    is_verified: bool = False
    notes: str | None = None


class ZoneRuleUpdate(BaseModel):
    base_value: float | None = None
    conditions: dict | None = None
    is_verified: bool | None = None
    notes: str | None = None


class PipelineStatusSchema(BaseModel):
    total_raw_sources: int = 0
    total_regulations: int = 0
    total_chunks: int = 0
    total_zone_rules: int = 0
    verified_rules: int = 0
    total_parcels_cached: int = 0
    total_assessments: int = 0
    total_feedback: int = 0
    last_ingestion: datetime | None = None


class IngestionLogSchema(BaseModel):
    id: uuid.UUID
    action: str
    previous_hash: str | None = None
    new_hash: str
    chunks_created: int
    rules_extracted: int
    started_at: datetime
    completed_at: datetime | None = None
