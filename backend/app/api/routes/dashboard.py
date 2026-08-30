from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard import DashboardService


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
SessionDependency = Annotated[Session, Depends(get_db)]


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    session: SessionDependency,
) -> DashboardOverviewResponse:
    return DashboardService.get_overview(session)

