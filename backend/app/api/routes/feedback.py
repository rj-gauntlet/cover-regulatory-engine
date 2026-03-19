"""User feedback API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.database import Assessment as AssessmentDB, Constraint as ConstraintDB, UserFeedback
from app.models.schemas import FeedbackRequest, FeedbackSchema

router = APIRouter()


@router.post("", response_model=FeedbackSchema)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
):
    """Submit user feedback on a constraint or assessment."""
    assessment = (await db.execute(
        select(AssessmentDB).where(AssessmentDB.id == request.assessment_id)
    )).scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if request.constraint_id:
        constraint = (await db.execute(
            select(ConstraintDB).where(ConstraintDB.id == request.constraint_id)
        )).scalar_one_or_none()
        if not constraint:
            raise HTTPException(status_code=404, detail="Constraint not found")
        if constraint.assessment_id != request.assessment_id:
            raise HTTPException(status_code=400, detail="Constraint does not belong to the given assessment")

    feedback = UserFeedback(
        constraint_id=request.constraint_id,
        assessment_id=request.assessment_id,
        rating=request.rating,
        comment=request.comment,
    )
    db.add(feedback)
    await db.commit()

    return FeedbackSchema(
        id=feedback.id,
        constraint_id=feedback.constraint_id,
        assessment_id=feedback.assessment_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
