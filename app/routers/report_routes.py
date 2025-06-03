from fastapi import APIRouter, Depends, status, HTTPException
from uuid import UUID
from typing import List, Dict, Any
from app.services.report_service import ReportService
from app.dependencies import get_current_user, get_current_active_admin_user
from app.dal.connection import get_db_connection
import pyodbc

# 定义 APIRouter
router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"]
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_report(
    conn: pyodbc.Connection = Depends(get_db_connection),
    report_service: ReportService = Depends(ReportService),
    current_user: dict = Depends(get_current_user)
):
    """
    提交举报 (依赖 get_current_user 认证，调用 ReportService.create_report)。
    """
    user_id = current_user['user_id']
    try:
        result = await report_service.create_report(conn, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/admin", response_model=List[Dict[str, Any]])
async def get_reports(
    conn: pyodbc.Connection = Depends(get_db_connection),
    report_service: ReportService = Depends(ReportService),
    current_admin: dict = Depends(get_current_active_admin_user)
):
    """
    管理员获取举报列表 (依赖 get_current_active_admin_user 认证，调用 ReportService.get_reports)。
    """
    try:
        reports = await report_service.get_reports(conn)
        return reports
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{report_id}/admin/handle", status_code=status.HTTP_204_NO_CONTENT)
async def handle_report(
    report_id: UUID,
    conn: pyodbc.Connection = Depends(get_db_connection),
    report_service: ReportService = Depends(ReportService),
    current_admin: dict = Depends(get_current_active_admin_user)
):
    """
    管理员处理举报 (依赖 get_current_active_admin_user 认证，调用 ReportService.handle_report)。
    """
    admin_id = current_admin['user_id']
    try:
        await report_service.handle_report(conn, report_id, admin_id)
        return {}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))