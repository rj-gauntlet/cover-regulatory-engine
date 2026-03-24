"""Assessment API endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_llm
from app.models.database import Assessment as AssessmentDB, Constraint as ConstraintDB, Parcel as ParcelDB
from app.models.schemas import AssessmentSchema, AssessmentRequest, ConstraintSchema, ParcelSchema
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
    geocoded = None

    if request.address:
        parcel, geocoded = await parcel_service.get_by_address(request.address)
    else:
        parcel = await parcel_service.get_by_apn(request.apn)

    if not parcel:
        error_body: dict = {
            "detail": "Could not find parcel. Ensure the address is within the City of Los Angeles.",
        }
        if geocoded:
            nearby = await parcel_service.get_nearby_addresses(
                geocoded["lat"], geocoded["lng"], request.address or ""
            )
            error_body["geocoded_lat"] = geocoded["lat"]
            error_body["geocoded_lng"] = geocoded["lng"]
            error_body["nearby_parcels"] = nearby
        return JSONResponse(status_code=404, content=error_body)

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

    parcel_result = await db.execute(
        select(ParcelDB).where(ParcelDB.id == assessment.parcel_id)
    )
    parcel_db = parcel_result.scalar_one_or_none()
    if not parcel_db:
        raise HTTPException(status_code=404, detail="Parcel not found for this assessment")

    parcel = ParcelSchema(
        id=parcel_db.id,
        apn=parcel_db.apn,
        address=parcel_db.address,
        zone_code=parcel_db.zone_code,
        zone_class=parcel_db.zone_class,
        height_district=parcel_db.height_district,
        specific_plan=parcel_db.specific_plan,
        overlay_zones=parcel_db.overlay_zones or [],
        lot_area_sqft=parcel_db.lot_area_sqft,
        lot_width_ft=parcel_db.lot_width_ft,
        lot_depth_ft=parcel_db.lot_depth_ft,
        centroid_lat=parcel_db.centroid_lat,
        centroid_lng=parcel_db.centroid_lng,
        community_plan_area=parcel_db.community_plan_area,
        geometry_geojson=parcel_db.geometry,
        building_footprints_geojson=parcel_db.building_footprints,
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


@router.get("/{assessment_id}/geojson")
async def export_geojson(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Export assessment as GeoJSON FeatureCollection."""
    result = await db.execute(
        select(AssessmentDB).where(AssessmentDB.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    parcel_result = await db.execute(
        select(ParcelDB).where(ParcelDB.id == assessment.parcel_id)
    )
    parcel = parcel_result.scalar_one_or_none()

    constraint_rows = await db.execute(
        select(ConstraintDB).where(ConstraintDB.assessment_id == assessment_id)
    )
    constraints = constraint_rows.scalars().all()

    features = []

    parcel_geom = parcel.geometry if parcel else None

    if parcel and parcel_geom:
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "parcel",
                "address": parcel.address,
                "apn": parcel.apn,
                "zone_code": parcel.zone_code,
                "zone_class": parcel.zone_class,
                "lot_area_sqft": parcel.lot_area_sqft,
            },
            "geometry": parcel_geom,
        })

    for c in constraints:
        geom = c.geometry_geojson or parcel_geom
        if geom is None:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "constraint",
                "category": c.category,
                "parameter": c.parameter,
                "value": c.value,
                "numeric_value": c.numeric_value,
                "unit": c.unit,
                "confidence": c.confidence,
                "determination_type": c.determination_type,
            },
            "geometry": geom,
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "assessment_id": str(assessment_id),
            "building_type": assessment.building_type,
            "overall_confidence": assessment.overall_confidence,
            "summary": assessment.summary,
        },
    }

    return JSONResponse(
        content=geojson,
        headers={
            "Content-Disposition": f'attachment; filename="assessment_{str(assessment_id)[:8]}.geojson"',
        },
    )
