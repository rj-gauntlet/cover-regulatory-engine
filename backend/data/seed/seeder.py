"""Seed the database with structured zone rules."""
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ZoneRule
from data.seed.zone_rules import ZONE_RULES

logger = logging.getLogger(__name__)


async def seed_zone_rules(db: AsyncSession) -> int:
    """Insert zone rules, adding any new zone classes not yet in the DB."""
    result = await db.execute(
        select(func.array_agg(func.distinct(ZoneRule.zone_class)))
    )
    existing_zones = set(result.scalar() or [])

    new_rules = [
        r for r in ZONE_RULES if r["zone_class"] not in existing_zones
    ]

    if not new_rules:
        logger.info(f"All zone classes already seeded ({len(existing_zones)} zones). Skipping.")
        return 0

    new_zones = {r["zone_class"] for r in new_rules}
    for rule_data in new_rules:
        db.add(ZoneRule(**rule_data))

    await db.flush()
    logger.info(f"Seeded {len(new_rules)} rules for new zones: {sorted(new_zones)}")
    return len(new_rules)
