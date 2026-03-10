"""User feedback API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.database import UserFeedback
from app.models.schemas import FeedbackRequest, FeedbackSchema

router = APIRouter()


@router.post("", response_model=FeedbackSchema)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
):
    """Submit user feedback on a constraint or assessment."""
    feedback = UserFeedback(
        constraint_id=request.constraint_id,
        assessment_id=request.assessment_id,
        rating=request.rating,
        comment=request.comment,
    )
    db.add(feedback)
    await db.flush()

    return FeedbackSchema(
        id=feedback.id,
        constraint_id=feedback.constraint_id,
        assessment_id=feedback.assessment_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
