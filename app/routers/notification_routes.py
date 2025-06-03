from fastapi import APIRouter, Depends, status, HTTPException
from uuid import UUID
from typing import List, Dict, Any, Optional
from app.services.system_notification_service import SystemNotificationService
from app.dependencies import get_current_user, get_current_active_admin_user
from app.dal.connection import get_db_connection
import pyodbc

# 定义 APIRouter
router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"]
)

@router.get("/me", response_model=List[Dict[str, Any]])
async def get_user_notifications(
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: SystemNotificationService = Depends(SystemNotificationService),
    current_user: dict = Depends(get_current_user)
):
    """
    获取当前用户通知列表。
    """
    user_id = current_user['user_id']
    try:
        notifications = await user_service.get_user_notifications(conn, user_id)
        return notifications
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_as_read(
    notification_id: UUID,
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: SystemNotificationService = Depends(SystemNotificationService),
    current_user: dict = Depends(get_current_user)
):
    """
    标记通知已读。
    """
    user_id = current_user['user_id']
    try:
        await user_service.mark_notification_as_read(conn, notification_id, user_id)
        return {}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: SystemNotificationService = Depends(SystemNotificationService),
    current_user: dict = Depends(get_current_user)
):
    """
    删除通知。
    """
    user_id = current_user['user_id']
    try:
        await user_service.delete_notification(conn, notification_id, user_id)
        return {}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/send", status_code=status.HTTP_201_CREATED)
async def send_notification(
    user_id: UUID,
    title: str,
    content: str,
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: SystemNotificationService = Depends(SystemNotificationService),
    current_admin: dict = Depends(get_current_active_admin_user)
):
    """
    管理员发送系统通知。
    """
    try:
        result = await user_service.send_notification(conn, user_id, title, content)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))