"""Layer 1: Structured rules lookup — deterministic, confidence 1.0."""
import logging

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ZoneRule
from app.models.schemas import ConstraintSchema, CitationSchema

logger = logging.getLogger(__name__)


class StructuredRuleLookup:
    """Query the ZoneRule table for known zone parameters."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def lookup(
        self, zone_class: str, building_type: str = "SFH"
    ) -> list[ConstraintSchema]:
        """Look up all structured rules for a zone class and building type."""
        if not zone_class:
            logger.warning("zone_class is empty or None — skipping structured rule lookup")
            return []

        result = await self.db.execute(
            select(ZoneRule).where(
                ZoneRule.zone_class == zone_class,
                or_(
                    ZoneRule.applies_to.contains([building_type]),
                    ZoneRule.applies_to.contains(["ALL"]),
                ),
            )
        )
        rules = result.scalars().all()

        constraints = []
        for rule in rules:
            citation = CitationSchema(
                section_number=rule.section_number,
                section_title=f"LAMC Sec. {rule.section_number}",
                relevant_text=rule.source_text,
                source_url=f"https://codelibrary.amlegal.com/codes/los_angeles/latest/lapz/0-0-0-0",
            )

            constraint = ConstraintSchema(
                category=rule.category,
                parameter=rule.parameter,
                rule_text=f"{rule.parameter.replace('_', ' ').title()}: {rule.base_value} {rule.unit}",
                value=f"{rule.base_value} {rule.unit}",
                numeric_value=rule.base_value,
                unit=rule.unit,
                confidence=1.0,
                source_layer="deterministic_lookup",
                determination_type="deterministic",
                citations=[citation],
                reasoning=f"Direct lookup from verified zone rule for {zone_class} zone (LAMC Sec. {rule.section_number})",
                zone_rule_id=rule.id,
            )

            if rule.conditions and "note" in rule.conditions:
                constraint.reasoning += f". Note: {rule.conditions['note']}"

            constraints.append(constraint)

        logger.info(f"Layer 1: Found {len(constraints)} structured rules for {zone_class}/{building_type}")
        return constraints
