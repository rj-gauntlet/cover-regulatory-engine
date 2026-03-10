"""Seed the database with structured zone rules."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ZoneRule
from data.seed.zone_rules import ZONE_RULES

logger = logging.getLogger(__name__)


async def seed_zone_rules(db: AsyncSession) -> int:
    """Insert zone rules if they don't already exist. Returns count of new rules."""
    existing = await db.execute(select(ZoneRule))
    existing_count = len(existing.scalars().all())

    if existing_count > 0:
        logger.info(f"Zone rules already seeded ({existing_count} rules). Skipping.")
        return 0

    count = 0
    for rule_data in ZONE_RULES:
        rule = ZoneRule(**rule_data)
        db.add(rule)
        count += 1

    await db.flush()
    logger.info(f"Seeded {count} zone rules.")
    return count
