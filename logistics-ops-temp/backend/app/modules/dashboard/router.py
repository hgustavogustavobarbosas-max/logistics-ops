from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    ctx: Annotated[AuthContext, Depends(require(Permission.DASHBOARD_READ))],
    db: DbSession,
) -> DashboardSummary:
    return service.get_summary(db, ctx)
