"""Rule Resolution Orchestrator — coordinates the three-layer hybrid engine."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Assessment as AssessmentDB, Constraint as ConstraintDB
from app.models.schemas import (
    AssessmentSchema, ConstraintSchema, ParcelSchema,
)
from app.services.engine.rules import StructuredRuleLookup
from app.services.engine.compute import ComputationEngine
from app.services.engine.retriever import RegulatoryRetriever
from app.services.engine.geometry import GeometryEngine
from app.services.engine.auto_seed import auto_seed_zone_rules
from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)


class RuleResolver:
    """Orchestrates the three-layer rule resolution engine.

    Layer 1: Deterministic lookup from ZoneRule table
    Layer 1b: Auto-seed — if Layer 1 returns nothing, fetch LAMC section,
              extract rules via LLM, save to zone_rules, then re-run Layer 1.
    Layer 2: Conditional computation against parcel dimensions
    Layer 3: RAG + LLM interpretation for ambiguous regulations
    """

    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm
        self.rules = StructuredRuleLookup(db)
        self.compute = ComputationEngine()
        self.retriever = RegulatoryRetriever(db, llm)
        self.geometry = GeometryEngine()

    async def assess(
        self,
        parcel: ParcelSchema,
        building_type: str = "SFH",
        project_inputs: dict | None = None,
    ) -> AssessmentSchema:
        """Run the full three-layer assessment for a parcel."""

        cached = await self._check_cache(parcel, building_type, project_inputs)
        if cached:
            logger.info(f"Assessment cache hit for {parcel.apn}/{building_type}")
            return cached

        logger.info(f"Running assessment for {parcel.apn} ({parcel.zone_class}) / {building_type}")

        # Layer 1: Deterministic lookup
        constraints = await self.rules.lookup(parcel.zone_class, building_type)
        logger.info(f"Layer 1 produced {len(constraints)} constraints")

        # Layer 1b: Auto-seed if Layer 1 found nothing
        if not constraints and parcel.zone_class:
            try:
                seeded = await auto_seed_zone_rules(parcel.zone_class, self.db, self.llm)
                if seeded > 0:
                    constraints = await self.rules.lookup(parcel.zone_class, building_type)
                    logger.info(f"Layer 1b auto-seeded {seeded} rules, re-lookup produced {len(constraints)} constraints")
            except Exception as e:
                logger.warning(f"Auto-seed failed for {parcel.zone_class}: {e}")

        # Layer 2: Conditional computation
        constraints = self.compute.refine_constraints(constraints, parcel, building_type)
        logger.info(f"After Layer 2: {len(constraints)} constraints")

        # Layer 3: RAG + LLM (only if we have embeddings and an API key)
        # Wrapped in a savepoint so SQL failures don't corrupt the transaction
        try:
            async with self.db.begin_nested():
                llm_constraints = await self.retriever.interpret_regulations(
                    parcel=parcel,
                    building_type=building_type,
                    existing_constraints=constraints,
                )
                constraints.extend(llm_constraints)
                logger.info(f"After Layer 3: {len(constraints)} total constraints")
        except Exception as e:
            logger.warning(f"Layer 3 failed (continuing with Layer 1+2 results): {e}")

        # Compute geometry (setbacks, buildable area)
        geometry_data = self.geometry.compute_setbacks(parcel, constraints)

        for constraint in constraints:
            if constraint.category == "setback" and geometry_data.get("setback_lines"):
                for feature in geometry_data["setback_lines"]["features"]:
                    if constraint.parameter == f"{feature['properties']['setback_type']}_setback":
                        constraint.geometry_geojson = feature["geometry"]

        # Compute overall confidence
        if constraints:
            overall_confidence = sum(c.confidence for c in constraints) / len(constraints)
        else:
            overall_confidence = 0.0

        # Build summary
        summary = self._build_summary(parcel, building_type, constraints)

        assessment = AssessmentSchema(
            parcel=parcel,
            building_type=building_type,
            project_inputs=project_inputs,
            constraints=constraints,
            overall_confidence=round(overall_confidence, 2),
            summary=summary,
        )

        # Persist to database
        await self._persist_assessment(assessment, parcel, geometry_data)

        return assessment

    def _build_summary(
        self,
        parcel: ParcelSchema,
        building_type: str,
        constraints: list[ConstraintSchema],
    ) -> str:
        """Generate a human-readable summary of the assessment."""
        deterministic = [c for c in constraints if c.determination_type == "deterministic"]
        interpreted = [c for c in constraints if c.determination_type != "deterministic"]

        lines = [
            f"Buildability assessment for {building_type} at {parcel.address or parcel.apn}",
            f"Zone: {parcel.zone_code} (class: {parcel.zone_class})",
            f"Lot area: {parcel.lot_area_sqft:,.0f} sqft" if parcel.lot_area_sqft else "",
            "",
            f"Found {len(deterministic)} deterministic constraints and "
            f"{len(interpreted)} interpreted constraints.",
        ]

        setbacks = [c for c in constraints if c.category == "setback"]
        if setbacks:
            lines.append("\nSetbacks:")
            for s in setbacks:
                lines.append(f"  - {s.rule_text}")

        height = [c for c in constraints if c.category == "height"]
        if height:
            lines.append("\nHeight:")
            for h in height:
                lines.append(f"  - {h.rule_text}")

        return "\n".join(line for line in lines if line)

    async def _check_cache(
        self,
        parcel: ParcelSchema,
        building_type: str,
        project_inputs: dict | None,
    ) -> AssessmentSchema | None:
        """Check if we already have a recent assessment for this parcel+type."""
        result = await self.db.execute(
            select(AssessmentDB).where(
                AssessmentDB.parcel_id == parcel.id,
                AssessmentDB.building_type == building_type,
            ).order_by(AssessmentDB.created_at.desc()).limit(1)
        )
        cached = result.scalar_one_or_none()
        if not cached:
            return None

        if project_inputs != cached.project_inputs:
            return None

        age = (datetime.now(timezone.utc).replace(tzinfo=None) - cached.created_at).total_seconds()
        if age > 3600:  # 1 hour cache
            return None

        constraint_rows = await self.db.execute(
            select(ConstraintDB).where(ConstraintDB.assessment_id == cached.id)
        )
        db_constraints = constraint_rows.scalars().all()

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
            id=cached.id,
            parcel=parcel,
            building_type=cached.building_type,
            project_inputs=cached.project_inputs,
            constraints=constraints,
            overall_confidence=cached.overall_confidence,
            summary=cached.summary,
            created_at=cached.created_at,
        )

    async def _persist_assessment(
        self,
        assessment: AssessmentSchema,
        parcel: ParcelSchema,
        geometry_data: dict,
    ) -> None:
        """Save assessment and constraints to the database."""
        db_assessment = AssessmentDB(
            id=assessment.id,
            parcel_id=parcel.id,
            building_type=assessment.building_type,
            project_inputs=assessment.project_inputs,
            overall_confidence=assessment.overall_confidence,
            summary=assessment.summary,
        )
        self.db.add(db_assessment)
        await self.db.flush()

        for constraint in assessment.constraints:
            citations_data = [c.model_dump(mode="json") for c in (constraint.citations or [])]
            db_constraint = ConstraintDB(
                id=constraint.id,
                assessment_id=assessment.id,
                category=constraint.category,
                parameter=constraint.parameter,
                rule_text=constraint.rule_text,
                value=constraint.value,
                numeric_value=constraint.numeric_value,
                unit=constraint.unit,
                confidence=constraint.confidence,
                source_layer=constraint.source_layer,
                determination_type=constraint.determination_type,
                citations=citations_data,
                reasoning=constraint.reasoning,
                geometry_geojson=constraint.geometry_geojson,
                zone_rule_id=constraint.zone_rule_id,
            )
            self.db.add(db_constraint)

        await self.db.flush()
