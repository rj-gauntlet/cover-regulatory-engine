"""Assessment API endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_llm
from app.models.database import Assessment as AssessmentDB, Constraint as ConstraintDB
from app.models.schemas import AssessmentSchema, AssessmentRequest, ConstraintSchema
from app.services.parcel.service import ParcelService
from app.services.engine.resolver import RuleResolver
from app.services.llm.base import LLMService

router = APIRouter()


@router.post("", response_model=AssessmentSchema)
async def create_assessment(
    request: AssessmentRequest,
    db: AsyncSession = Depends(get_session),
    llm: LLMService = Depends(get_llm),
):
    """Create a buildability assessment for a parcel."""
    if not request.address and not request.apn:
        raise HTTPException(status_code=400, detail="Provide either an address or APN")

    parcel_service = ParcelService(db)

    if request.address:
        parcel = await parcel_service.get_by_address(request.address)
    else:
        parcel = await parcel_service.get_by_apn(request.apn)

    if not parcel:
        raise HTTPException(
            status_code=404,
            detail="Could not find parcel. Ensure the address is within the City of Los Angeles.",
        )

    resolver = RuleResolver(db, llm)
    assessment = await resolver.assess(
        parcel=parcel,
        building_type=request.building_type,
        project_inputs=request.project_inputs,
    )

    return assessment


@router.get("/{assessment_id}", response_model=AssessmentSchema)
async def get_assessment(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Retrieve a previous assessment."""
    result = await db.execute(
        select(AssessmentDB).where(AssessmentDB.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    constraint_rows = await db.execute(
        select(ConstraintDB).where(ConstraintDB.assessment_id == assessment_id)
    )
    db_constraints = constraint_rows.scalars().all()

    from app.services.parcel.service import ParcelService
    parcel_service = ParcelService(db)
    parcel = await parcel_service.get_by_apn(
        (await db.execute(
            select(AssessmentDB).where(AssessmentDB.id == assessment_id)
        )).scalar_one().parcel_id
    )

    constraints = [
        ConstraintSchema(
            id=c.id,
            category=c.category,
            parameter=c.parameter,
            rule_text=c.rule_text,
            value=c.value,
            numeric_value=c.numeric_value,
            unit=c.unit,
            confidence=c.confidence,
            source_layer=c.source_layer,
            determination_type=c.determination_type,
            citations=c.citations or [],
            reasoning=c.reasoning,
            geometry_geojson=c.geometry_geojson,
            zone_rule_id=c.zone_rule_id,
        )
        for c in db_constraints
    ]

    return AssessmentSchema(
        id=assessment.id,
        parcel=parcel,
        building_type=assessment.building_type,
        project_inputs=assessment.project_inputs,
        constraints=constraints,
        overall_confidence=assessment.overall_confidence,
        summary=assessment.summary,
        created_at=assessment.created_at,
    )
