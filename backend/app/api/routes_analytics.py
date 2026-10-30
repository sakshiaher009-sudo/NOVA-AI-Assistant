"""NOVA — Analytics Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id
from app.schemas.analytics import AnalyticsOverview
from app.services.analytics_service import get_analytics

router = APIRouter(tags=["analytics"])


@router.get("/api/analytics", response_model=AnalyticsOverview)
async def analytics(user_id: str = Depends(get_current_user_id)):
    """Get system analytics for the authenticated user."""
    return await get_analytics(user_id=user_id)
