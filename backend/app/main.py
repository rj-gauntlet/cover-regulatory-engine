import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assess, parcel, chat, feedback, admin
from app.core.config import settings
from app.core.database import engine, async_session, Base
from app.models.database import (  # noqa: F401
    RawSource, ParsedRegulation, RegulatoryChunk, ZoneRule,
    Parcel, Assessment, Constraint, ChatSession, ChatMessage,
    UserFeedback, IngestionLog,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables ready.")

    from data.seed.seeder import seed_zone_rules
    async with async_session() as session:
        count = await seed_zone_rules(session)
        if count > 0:
            await session.commit()
            logger.info(f"Seeded {count} zone rules.")
        else:
            logger.info("Zone rules already seeded.")

    yield


app = FastAPI(
    title="Cover Regulatory Engine",
    description="Home building regulatory engine for LA City residential parcels",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assess.router, prefix="/api/assess", tags=["Assessment"])
app.include_router(parcel.router, prefix="/api/parcel", tags=["Parcel"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
