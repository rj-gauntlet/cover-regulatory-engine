import uuid
from datetime import datetime, date, timezone

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime, Date,
    ForeignKey, JSON, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.core.config import settings


def _utcnow() -> datetime:
    """Naive UTC timestamp compatible with TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RawSource(Base):
    __tablename__ = "raw_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "html" | "pdf"
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_sources.id"), nullable=True)

    regulations: Mapped[list["ParsedRegulation"]] = relationship(back_populates="raw_source")


class ParsedRegulation(Base):
    __tablename__ = "parsed_regulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_sources.id"), nullable=False)
    section_number: Mapped[str] = mapped_column(String(50), nullable=False)
    section_title: Mapped[str] = mapped_column(Text, nullable=False)
    article: Mapped[str] = mapped_column(String(100), nullable=False)
    chapter: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_codes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_source: Mapped["RawSource"] = relationship(back_populates="regulations")
    chunks: Mapped[list["RegulatoryChunk"]] = relationship(back_populates="regulation")
    zone_rules: Mapped[list["ZoneRule"]] = relationship(back_populates="regulation")

    __table_args__ = (
        Index("ix_parsed_regulations_zone_codes", "zone_codes", postgresql_using="gin"),
        Index("ix_parsed_regulations_section", "section_number"),
    )


class RegulatoryChunk(Base):
    __tablename__ = "regulatory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parsed_regulations.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions), nullable=True)
    zone_codes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    section_number: Mapped[str] = mapped_column(String(50), nullable=False)

    regulation: Mapped["ParsedRegulation"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_regulatory_chunks_zone_codes", "zone_codes", postgresql_using="gin"),
    )


class ZoneRule(Base):
    __tablename__ = "zone_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_class: Mapped[str] = mapped_column(String(20), nullable=False)
    parameter: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    base_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applies_to: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=lambda: ["ALL"])
    section_number: Mapped[str] = mapped_column(String(50), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    regulation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parsed_regulations.id"), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    regulation: Mapped["ParsedRegulation | None"] = relationship(back_populates="zone_rules")

    __table_args__ = (
        Index("ix_zone_rules_zone_class", "zone_class"),
        Index("ix_zone_rules_category", "category"),
        Index("ix_zone_rules_lookup", "zone_class", "parameter"),
    )


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    apn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_code: Mapped[str] = mapped_column(String(30), nullable=False)
    zone_class: Mapped[str] = mapped_column(String(20), nullable=False)
    height_district: Mapped[str | None] = mapped_column(String(10), nullable=True)
    specific_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    overlay_zones: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    lot_area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_width_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_depth_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    building_footprints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    centroid_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    community_plan_area: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    cache_ttl_days: Mapped[int] = mapped_column(Integer, default=30)

    assessments: Mapped[list["Assessment"]] = relationship(back_populates="parcel")

    __table_args__ = (
        Index("ix_parcels_zone_class", "zone_class"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parcels.id"), nullable=False)
    building_type: Mapped[str] = mapped_column(String(30), nullable=False)
    project_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    parcel: Mapped["Parcel"] = relationship(back_populates="assessments")
    constraints: Mapped[list["Constraint"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="assessment")
    feedback: Mapped[list["UserFeedback"]] = relationship(back_populates="assessment")


class Constraint(Base):
    __tablename__ = "constraints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    parameter: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source_layer: Mapped[str] = mapped_column(String(30), nullable=False)
    determination_type: Mapped[str] = mapped_column(String(20), nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    geometry_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    zone_rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("zone_rules.id"), nullable=True)

    assessment: Mapped["Assessment"] = relationship(back_populates="constraints")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    assessment: Mapped["Assessment"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    constraint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("constraints.id"), nullable=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    assessment: Mapped["Assessment"] = relationship(back_populates="feedback")


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_sources.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rules_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
