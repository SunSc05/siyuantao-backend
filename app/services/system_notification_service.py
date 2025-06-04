import pyodbc
from uuid import UUID
from typing import Optional, Callable, Awaitable, List, Dict, Any  # 添加 Any 导入
import logging
from app.dal.system_notification_dal import SystemNotificationDAL
from app.exceptions import NotFoundError, DALError, ForbiddenError

logger = logging.getLogger(__name__)

class SystemNotificationService:
    def __init__(self, notification_dal: SystemNotificationDAL):
        self.notification_dal = notification_dal

    async def send_notification(self, conn: pyodbc.Connection, user_id: UUID, title: str, content: str) -> Dict[str, str]:
        """
        发送系统通知给指定用户。

        Args:
            conn: 数据库连接对象。
            user_id: 接收者用户 ID。
            title: 通知标题。
            content: 通知内容。

        Returns:
            操作结果（包含成功信息或错误信息）。

        Raises:
            NotFoundError: 如果目标用户不存在。
            DALError: 如果发生其他数据库错误。
        """
        logger.info(f"尝试发送系统通知给用户 {user_id}，标题: {title}")
        try:
            result = await self.notification_dal.send_system_notification(conn, user_id, title, content)
            logger.info(f"系统通知发送成功给用户 {user_id}")
            return result
        except (NotFoundError, DALError) as e:
            logger.error(f"发送通知时出错: {e}")
            raise e

    async def get_user_notifications(self, conn: pyodbc.Connection, user_id: UUID, is_read: Optional[bool] = None, page_number: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """
        获取用户通知列表。

        Args:
            conn: 数据库连接对象。
            user_id: 用户 ID。
            is_read: 是否已读（0=未读，1=已读，None=不筛选）。
            page_number: 页码（从 1 开始）。
            page_size: 每页数量。

        Returns:
            通知列表（包含总记录数）。

        Raises:
            NotFoundError: 如果用户不存在。
            DALError: 如果发生数据库错误。
        """
        logger.info(f"获取用户 {user_id} 的通知列表，已读状态: {is_read}，分页: {page_number}/{page_size}")
        try:
            result = await self.notification_dal.get_user_notifications(conn, user_id, is_read, page_number, page_size)
            logger.info(f"成功获取用户 {user_id} 的通知列表")
            return result
        except (NotFoundError, DALError) as e:
            logger.error(f"获取通知列表时出错: {e}")
            raise e

    async def mark_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        标记通知为已读。

        Args:
            conn: 数据库连接对象。
            notification_id: 通知 ID。
            user_id: 接收者用户 ID（用于权限校验）。

        Returns:
            操作是否成功。

        Raises:
            NotFoundError: 如果通知不存在。
            ForbiddenError: 如果无权限标记此通知。
            DALError: 如果发生数据库错误。
        """
        logger.info(f"标记通知 {notification_id} 为已读（用户 {user_id}）")
        try:
            result = await self.notification_dal.mark_notification_as_read(conn, notification_id, user_id)
            logger.info(f"通知 {notification_id} 已成功标记为已读（用户 {user_id}）")
            return result
        except (NotFoundError, ForbiddenError, DALError) as e:
            logger.error(f"标记通知为已读时出错: {e}")
            raise e

    async def delete_notification(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        逻辑删除通知。

        Args:
            conn: 数据库连接对象。
            notification_id: 通知 ID。
            user_id: 用户 ID（用于权限校验）。

        Returns:
            操作是否成功。

        Raises:
            NotFoundError: 如果通知不存在。
            ForbiddenError: 如果无权限删除此通知。
            DALError: 如果发生数据库错误。
        """
        logger.info(f"逻辑删除通知 {notification_id}（用户 {user_id}）")
        try:
            result = await self.notification_dal.delete_notification(conn, notification_id, user_id)
            logger.info(f"通知 {notification_id} 已成功逻辑删除（用户 {user_id}）")
            return result
        except (NotFoundError, ForbiddenError, DALError) as e:
            logger.error(f"删除通知时出错: {e}")
            raise e