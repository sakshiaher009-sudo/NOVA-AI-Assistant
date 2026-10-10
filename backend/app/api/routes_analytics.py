"""NOVA — Analytics Routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.analytics_service import get_analytics
from app.schemas.analytics import AnalyticsOverview

router = APIRouter(tags=["analytics"])


@router.get("/api/analytics", response_model=AnalyticsOverview)
async def analytics():
    """Get system analytics."""
    return await get_analytics()
