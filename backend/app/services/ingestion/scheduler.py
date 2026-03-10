"""Change detection scheduler for regulatory data updates."""
import hashlib
import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import RawSource, IngestionLog
from app.services.ingestion.scraper import scrape_section, LAMC_ZONING_SECTIONS

logger = logging.getLogger(__name__)


async def check_for_changes(db: AsyncSession) -> list[dict]:
    """Compare current source hashes against stored hashes.
    Returns list of sections that have changed.
    """
    changes = []

    for section_number in LAMC_ZONING_SECTIONS:
        latest_source = await db.execute(
            select(RawSource)
            .where(RawSource.source_url.contains(section_number.replace(".", "")))
            .order_by(RawSource.fetched_at.desc())
            .limit(1)
        )
        stored = latest_source.scalar_one_or_none()

        scraped = await scrape_section(section_number)
        if not scraped:
            continue

        if stored and stored.content_hash == scraped["content_hash"]:
            log = IngestionLog(
                raw_source_id=stored.id,
                action="no_change",
                previous_hash=stored.content_hash,
                new_hash=scraped["content_hash"],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            db.add(log)
        else:
            changes.append({
                "section_number": section_number,
                "previous_hash": stored.content_hash if stored else None,
                "new_hash": scraped["content_hash"],
                "data": scraped,
            })
            log = IngestionLog(
                raw_source_id=stored.id if stored else None,
                action="change_detected",
                previous_hash=stored.content_hash if stored else None,
                new_hash=scraped["content_hash"],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            db.add(log)

    await db.commit()
    return changes
