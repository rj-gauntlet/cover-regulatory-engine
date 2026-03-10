"""Initialize the database: run migrations, seed data, and optionally run ingestion."""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, async_session, Base
from app.models.database import *  # noqa: F401, F403 — ensure all models are imported
from data.seed.seeder import seed_zone_rules

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init():
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created.")

    logger.info("Seeding zone rules...")
    async with async_session() as session:
        count = await seed_zone_rules(session)
        await session.commit()
        logger.info(f"Seeded {count} zone rules.")

    logger.info("Database initialization complete.")


async def init_with_ingestion():
    await init()

    logger.info("Running regulatory data ingestion...")
    from app.services.ingestion.embedder import run_full_ingestion

    async with async_session() as session:
        stats = await run_full_ingestion(session)
        logger.info(f"Ingestion stats: {stats}")


if __name__ == "__main__":
    if "--with-ingestion" in sys.argv:
        asyncio.run(init_with_ingestion())
    else:
        asyncio.run(init())
