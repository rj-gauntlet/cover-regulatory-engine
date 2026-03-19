from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.llm.base import LLMService
from app.services.llm.openai_provider import get_llm_service


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_llm() -> LLMService:
    return get_llm_service()
