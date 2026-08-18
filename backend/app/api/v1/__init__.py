from fastapi import APIRouter

from app.api.v1 import (
    admin_attendance,
    admin_audit,
    admin_reports,
    admin_users,
    admin_workspace,
    attendance,
    auth,
    health,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(attendance.router)
api_router.include_router(admin_attendance.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_workspace.router)
api_router.include_router(admin_reports.router)
api_router.include_router(admin_audit.router)

__all__ = ["api_router"]
