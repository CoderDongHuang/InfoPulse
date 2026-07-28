"""AI copywriting workflow."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.analysis_history import AnalysisHistory
from app.models.user import User
from app.schemas.workflows import MouthpieceRequest
from app.services.workflows import generate_mouthpiece

router = APIRouter(prefix="/api/v1/mouthpiece", tags=["Mouthpiece"])


@router.post("/generate")
async def generate(payload: MouthpieceRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await generate_mouthpiece(payload.model_dump())
    history = AnalysisHistory(
        user_id=current_user.id,
        module="mouthpiece",
        input_params=payload.model_dump(),
        output_result=result,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)
    await db.commit()
    return result
