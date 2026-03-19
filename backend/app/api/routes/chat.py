"""Chat API endpoints with SSE streaming."""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_llm
from app.core.database import async_session as session_factory
from app.models.database import (
    Assessment as AssessmentDB,
    ChatSession,
    ChatMessage,
    Constraint as ConstraintDB,
)
from app.models.schemas import ChatRequest, ChatMessageSchema
from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()

CHAT_SYSTEM_PROMPT = """You are a zoning regulation expert assistant for the City of Los Angeles.
You are helping an architect or engineer understand the buildability assessment for a specific parcel.

You have access to the assessment results and relevant regulatory text. Answer questions accurately,
cite specific LAMC sections when possible, and clearly distinguish between verified facts and
interpretations.

If you are uncertain about something, say so explicitly rather than guessing.
Be concise but thorough. Use technical language appropriate for architects and engineers."""


@router.post("/{assessment_id}")
async def chat_with_assessment(
    assessment_id: uuid.UUID,
    request: ChatRequest,
    db: AsyncSession = Depends(get_session),
    llm: LLMService = Depends(get_llm),
):
    """Send a follow-up question about an assessment. Returns SSE stream."""
    assessment_result = await db.execute(
        select(AssessmentDB).where(AssessmentDB.id == assessment_id)
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    constraint_rows = await db.execute(
        select(ConstraintDB).where(ConstraintDB.assessment_id == assessment_id)
    )
    constraints = constraint_rows.scalars().all()

    session_result = await db.execute(
        select(ChatSession)
        .where(ChatSession.assessment_id == assessment_id)
        .order_by(ChatSession.created_at.desc())
        .limit(1)
    )
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        chat_session = ChatSession(assessment_id=assessment_id)
        db.add(chat_session)
        await db.flush()

    user_msg = ChatMessage(
        session_id=chat_session.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.flush()

    prev_messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at)
    )
    prev_messages = prev_messages_result.scalars().all()

    constraints_context = "\n".join(
        f"- {c.parameter}: {c.value} (confidence: {c.confidence}, "
        f"type: {c.determination_type}, source: LAMC Sec. "
        f"{c.citations[0].get('section_number', 'N/A') if c.citations and isinstance(c.citations[0], dict) else 'N/A'})"
        for c in constraints
    )

    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "system", "content": f"Assessment context:\n{assessment.summary}\n\nConstraints:\n{constraints_context}"},
    ]

    for msg in prev_messages:
        messages.append({"role": msg.role, "content": msg.content})

    session_id = chat_session.id

    async def generate():
        full_response = ""
        try:
            async for token in llm.complete_stream(messages=messages, temperature=0.1):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("LLM stream failed")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            if full_response:
                async with session_factory() as save_db:
                    assistant_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=full_response,
                    )
                    save_db.add(assistant_msg)
                    await save_db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{assessment_id}/history", response_model=list[ChatMessageSchema])
async def get_chat_history(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get chat history for an assessment."""
    session_result = await db.execute(
        select(ChatSession)
        .where(ChatSession.assessment_id == assessment_id)
        .order_by(ChatSession.created_at.desc())
        .limit(1)
    )
    chat_session = session_result.scalar_one_or_none()
    if not chat_session:
        return []

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()

    return [
        ChatMessageSchema(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            citations=msg.citations,
            created_at=msg.created_at,
        )
        for msg in messages
    ]
