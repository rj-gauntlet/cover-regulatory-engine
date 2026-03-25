"""Admin panel API endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.deps import get_session
from app.models.database import (
    RawSource, ParsedRegulation, RegulatoryChunk, ZoneRule,
    Parcel, Assessment, Constraint, UserFeedback, IngestionLog,
    GeocodingCache,
)
from app.models.schemas import (
    PipelineStatusSchema, ZoneRuleSchema, ZoneRuleUpdate,
    IngestionLogSchema, FeedbackSchema,
)

router = APIRouter()


@router.get("/pipeline/status", response_model=PipelineStatusSchema)
async def pipeline_status(db: AsyncSession = Depends(get_session)):
    """Get ingestion pipeline status and statistics."""
    raw_count = (await db.execute(select(func.count(RawSource.id)))).scalar() or 0
    reg_count = (await db.execute(select(func.count(ParsedRegulation.id)))).scalar() or 0
    chunk_count = (await db.execute(select(func.count(RegulatoryChunk.id)))).scalar() or 0
    rule_count = (await db.execute(select(func.count(ZoneRule.id)))).scalar() or 0
    verified_count = (await db.execute(
        select(func.count(ZoneRule.id)).where(ZoneRule.is_verified == True)  # noqa: E712
    )).scalar() or 0
    parcel_count = (await db.execute(select(func.count(Parcel.id)))).scalar() or 0
    assess_count = (await db.execute(select(func.count(Assessment.id)))).scalar() or 0
    feedback_count = (await db.execute(select(func.count(UserFeedback.id)))).scalar() or 0

    last_log = await db.execute(
        select(IngestionLog).order_by(IngestionLog.completed_at.desc()).limit(1)
    )
    last = last_log.scalar_one_or_none()

    return PipelineStatusSchema(
        total_raw_sources=raw_count,
        total_regulations=reg_count,
        total_chunks=chunk_count,
        total_zone_rules=rule_count,
        verified_rules=verified_count,
        total_parcels_cached=parcel_count,
        total_assessments=assess_count,
        total_feedback=feedback_count,
        last_ingestion=last.completed_at if last else None,
    )


@router.get("/pipeline/logs", response_model=list[IngestionLogSchema])
async def pipeline_logs(
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_session),
):
    """Get ingestion audit logs."""
    result = await db.execute(
        select(IngestionLog).order_by(IngestionLog.started_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        IngestionLogSchema(
            id=log.id,
            action=log.action,
            previous_hash=log.previous_hash,
            new_hash=log.new_hash,
            chunks_created=log.chunks_created,
            rules_extracted=log.rules_extracted,
            started_at=log.started_at,
            completed_at=log.completed_at,
        )
        for log in logs
    ]


@router.post("/pipeline/trigger")
async def trigger_ingestion(
    mode: str = Query(default="auto", enum=["auto", "scrape", "llm"]),
    db: AsyncSession = Depends(get_session),
):
    """Manually trigger a re-ingestion of regulatory data.

    Modes:
    - auto: try scraper first, fall back to LLM-based generation
    - scrape: only use the HTML scraper (amlegal.com)
    - llm: only use LLM-generated regulatory text
    """
    from app.services.ingestion.embedder import run_full_ingestion, run_llm_ingestion

    stats = None
    method_used = ""

    if mode in ("auto", "scrape"):
        try:
            stats = await run_full_ingestion(db)
            method_used = "scrape"
            if stats.get("sections_scraped", 0) == 0 and mode == "auto":
                stats = None
        except Exception as exc:
            logger.warning(f"Scraper failed: {exc}")
            if mode == "scrape":
                raise HTTPException(status_code=500, detail=f"Scrape ingestion failed: {exc}")

    if stats is None and mode in ("auto", "llm"):
        try:
            stats = await run_llm_ingestion(db)
            method_used = "llm"
        except Exception as exc:
            logger.exception("LLM ingestion failed")
            raise HTTPException(status_code=500, detail=f"LLM ingestion failed: {exc}")

    if stats is None:
        raise HTTPException(status_code=500, detail="No ingestion method succeeded")

    return {
        "status": "complete",
        "method": method_used,
        "stats": stats,
    }


@router.get("/rules", response_model=list[ZoneRuleSchema])
async def list_rules(
    zone_class: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """Browse structured zone rules."""
    query = select(ZoneRule)
    if zone_class:
        query = query.where(ZoneRule.zone_class == zone_class)
    if category:
        query = query.where(ZoneRule.category == category)
    query = query.order_by(ZoneRule.zone_class, ZoneRule.category, ZoneRule.parameter)

    result = await db.execute(query)
    rules = result.scalars().all()

    return [
        ZoneRuleSchema(
            id=rule.id,
            zone_class=rule.zone_class,
            parameter=rule.parameter,
            category=rule.category,
            base_value=rule.base_value,
            unit=rule.unit,
            conditions=rule.conditions,
            applies_to=rule.applies_to,
            section_number=rule.section_number,
            source_text=rule.source_text,
            is_verified=rule.is_verified,
            notes=rule.notes,
        )
        for rule in rules
    ]


@router.put("/rules/{rule_id}", response_model=ZoneRuleSchema)
async def update_rule(
    rule_id: uuid.UUID,
    update: ZoneRuleUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Edit or verify a structured rule."""
    result = await db.execute(select(ZoneRule).where(ZoneRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if update.base_value is not None:
        rule.base_value = update.base_value
    if update.conditions is not None:
        rule.conditions = update.conditions
    if update.is_verified is not None:
        rule.is_verified = update.is_verified
    if update.notes is not None:
        rule.notes = update.notes

    await db.flush()

    # Invalidate cached assessments for parcels using this zone class
    # so the 7-day cache doesn't serve stale data after a rule edit
    from sqlalchemy import delete
    stale = await db.execute(
        select(Assessment.id).join(Parcel).where(Parcel.zone_class == rule.zone_class)
    )
    stale_ids = [row[0] for row in stale.all()]
    if stale_ids:
        await db.execute(delete(Constraint).where(Constraint.assessment_id.in_(stale_ids)))
        await db.execute(delete(Assessment).where(Assessment.id.in_(stale_ids)))
        await db.flush()

    return ZoneRuleSchema(
        id=rule.id,
        zone_class=rule.zone_class,
        parameter=rule.parameter,
        category=rule.category,
        base_value=rule.base_value,
        unit=rule.unit,
        conditions=rule.conditions,
        applies_to=rule.applies_to,
        section_number=rule.section_number,
        source_text=rule.source_text,
        is_verified=rule.is_verified,
        notes=rule.notes,
    )


@router.get("/regulations")
async def list_regulations(
    zone_code: str | None = None,
    topic: str | None = None,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_session),
):
    """Browse parsed regulations."""
    query = select(ParsedRegulation)
    if zone_code:
        query = query.where(ParsedRegulation.zone_codes.contains([zone_code]))
    if topic:
        query = query.where(ParsedRegulation.topic == topic)
    query = query.order_by(ParsedRegulation.section_number).limit(limit)

    result = await db.execute(query)
    regulations = result.scalars().all()

    return [
        {
            "id": str(reg.id),
            "section_number": reg.section_number,
            "section_title": reg.section_title,
            "article": reg.article,
            "chapter": reg.chapter,
            "zone_codes": reg.zone_codes,
            "topic": reg.topic,
            "body_text": ((reg.body_text or "")[:500] + "...") if len(reg.body_text or "") > 500 else (reg.body_text or ""),
            "parsed_at": reg.parsed_at.isoformat(),
        }
        for reg in regulations
    ]


@router.get("/feedback", response_model=list[FeedbackSchema])
async def list_feedback(
    rating: str | None = None,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_session),
):
    """Browse user feedback."""
    query = select(UserFeedback)
    if rating:
        query = query.where(UserFeedback.rating == rating)
    query = query.order_by(UserFeedback.created_at.desc()).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()

    return [
        FeedbackSchema(
            id=fb.id,
            constraint_id=fb.constraint_id,
            assessment_id=fb.assessment_id,
            rating=fb.rating,
            comment=fb.comment,
            created_at=fb.created_at,
        )
        for fb in items
    ]


@router.get("/stats")
async def system_stats(db: AsyncSession = Depends(get_session)):
    """System statistics summary."""
    status = await pipeline_status(db)
    zone_classes = (await db.execute(
        select(ZoneRule.zone_class).distinct().order_by(ZoneRule.zone_class)
    )).scalars().all()
    return {
        "pipeline": status.model_dump(),
        "zone_classes_covered": list(zone_classes),
        "building_types_supported": ["SFH", "ADU", "Guest House"],
    }


@router.get("/cache-stats")
async def cache_stats(db: AsyncSession = Depends(get_session)):
    """Cache statistics for monitoring."""
    geocoding_count = (await db.execute(
        select(func.count(GeocodingCache.id))
    )).scalar() or 0
    parcel_count = (await db.execute(
        select(func.count(Parcel.id))
    )).scalar() or 0
    assessment_count = (await db.execute(
        select(func.count(Assessment.id))
    )).scalar() or 0

    # Recent cache activity (last 24h)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    recent_geocoding = (await db.execute(
        select(func.count(GeocodingCache.id)).where(GeocodingCache.cached_at >= cutoff)
    )).scalar() or 0
    recent_parcels = (await db.execute(
        select(func.count(Parcel.id)).where(Parcel.cached_at >= cutoff)
    )).scalar() or 0
    recent_assessments = (await db.execute(
        select(func.count(Assessment.id)).where(Assessment.created_at >= cutoff)
    )).scalar() or 0

    return {
        "geocoding_cache": {"total": geocoding_count, "last_24h": recent_geocoding},
        "parcel_cache": {"total": parcel_count, "last_24h": recent_parcels},
        "assessment_cache": {"total": assessment_count, "last_24h": recent_assessments},
    }
