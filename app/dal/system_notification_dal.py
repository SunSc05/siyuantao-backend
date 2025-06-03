import pyodbc
from app.dal.base import execute_query  # 保持类型提示
from app.exceptions import NotFoundError, ForbiddenError, DALError
from uuid import UUID
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class SystemNotificationDAL:
    def __init__(self, execute_query_func):
        """
        初始化 SystemNotificationDAL，依赖注入数据库查询执行函数
        :param execute_query_func: 数据库查询执行函数（由上层注入，如 Service 层）
        """
        self.execute_query_func = execute_query_func

    async def send_system_notification(
        self, 
        conn: pyodbc.Connection, 
        user_id: UUID, 
        title: str, 
        content: str
    ) -> Dict[str, str]:
        """
        发送系统通知给指定用户（调用 sp_SendSystemNotification 存储过程）
        :param conn: 数据库连接对象
        :param user_id: 接收者用户 ID
        :param title: 通知标题
        :param content: 通知内容
        :return: 操作结果（包含成功信息或错误信息）
        """
        logger.debug(f"DAL: 尝试发送系统通知给用户 {user_id}，标题: {title}")
        sql = "{CALL sp_SendSystemNotification(?, ?, ?)}"
        try:
            result = await self.execute_query_func(
                conn, sql, (user_id, title, content), fetchone=True
            )
            logger.debug(f"DAL: sp_SendSystemNotification 返回结果: {result}")

            if not result or not isinstance(result, dict):
                raise DALError("发送通知失败：数据库返回无效结果")

            # 检查存储过程返回的错误信息
            error_msg = result.get("Result")
            if "目标用户不存在" in error_msg:
                raise NotFoundError("目标用户不存在，无法发送通知")
            if "系统通知发送成功" in error_msg:
                return result
            raise DALError(f"发送通知失败：{error_msg}")

        except pyodbc.Error as e:
            logger.error(f"DAL: 发送通知时数据库错误: {e}")
            raise DALError(f"数据库错误：{e}") from e

    async def get_user_notifications(
        self, 
        conn: pyodbc.Connection, 
        user_id: UUID, 
        is_read: Optional[bool] = None, 
        page_number: int = 1, 
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取用户通知列表（调用 sp_GetUserNotifications 存储过程）
        :param conn: 数据库连接对象
        :param user_id: 用户 ID
        :param is_read: 是否已读（0=未读，1=已读，None=不筛选）
        :param page_number: 页码（从 1 开始）
        :param page_size: 每页数量
        :return: 通知列表（包含总记录数）
        """
        logger.debug(f"DAL: 获取用户 {user_id} 的通知列表，已读状态: {is_read}，分页: {page_number}/{page_size}")
        sql = "{CALL sp_GetUserNotifications(?, ?, ?, ?)}"
        try:
            result = await self.execute_query_func(
                conn, sql, (user_id, is_read, page_number, page_size), fetchall=True
            )
            logger.debug(f"DAL: sp_GetUserNotifications 返回结果: {result}")

            if not result:
                return []
            if isinstance(result[0], dict) and "用户不存在" in result[0].values():
                raise NotFoundError("用户不存在")
            return result

        except pyodbc.Error as e:
            logger.error(f"DAL: 获取通知时数据库错误: {e}")
            raise DALError(f"数据库错误：{e}") from e

    async def mark_notification_as_read(
        self, 
        conn: pyodbc.Connection, 
        notification_id: UUID, 
        user_id: UUID
    ) -> bool:
        """
        标记通知为已读（调用 sp_MarkNotificationAsRead 存储过程）
        :param conn: 数据库连接对象
        :param notification_id: 通知 ID
        :param user_id: 接收者用户 ID（用于权限校验）
        :return: 操作是否成功
        """
        logger.debug(f"DAL: 标记通知 {notification_id} 为已读（用户 {user_id}）")
        sql = "{CALL sp_MarkNotificationAsRead(?, ?)}"
        try:
            result = await self.execute_query_func(
                conn, sql, (notification_id, user_id), fetchone=True
            )
            logger.debug(f"DAL: sp_MarkNotificationAsRead 返回结果: {result}")

            if not result or not isinstance(result, dict):
                raise DALError("标记已读失败：数据库返回无效结果")

            error_msg = result.get("Result")
            if "通知不存在" in error_msg:
                raise NotFoundError("通知不存在")
            if "无权标记" in error_msg:
                raise ForbiddenError("无权限标记此通知")
            if "已读成功" in error_msg:
                return True
            return False  # 其他情况（如已读状态未变化）

        except pyodbc.Error as e:
            logger.error(f"DAL: 标记已读时数据库错误: {e}")
            raise DALError(f"数据库错误：{e}") from e

    async def delete_notification(
        self, 
        conn: pyodbc.Connection, 
        notification_id: UUID, 
        user_id: UUID
    ) -> bool:
        """
        逻辑删除通知（调用 sp_DeleteNotification 存储过程）
        :param conn: 数据库连接对象
        :param notification_id: 通知 ID
        :param user_id: 用户 ID（用于权限校验）
        :return: 操作是否成功
        """
        logger.debug(f"DAL: 逻辑删除通知 {notification_id}（用户 {user_id}）")
        sql = "{CALL sp_DeleteNotification(?, ?)}"
        try:
            result = await self.execute_query_func(
                conn, sql, (notification_id, user_id), fetchone=True
            )
            logger.debug(f"DAL: sp_DeleteNotification 返回结果: {result}")

            if not result or not isinstance(result, dict):
                raise DALError("删除通知失败：数据库返回无效结果")

            error_msg = result.get("Result")
            if "通知不存在" in error_msg:
                raise NotFoundError("通知不存在")
            if "无权删除" in error_msg:
                raise ForbiddenError("无权限删除此通知")
            if "已标记为删除" in error_msg:
                return True
            return False  # 其他情况（如已删除状态未变化）

        except pyodbc.Error as e:
            logger.error(f"DAL: 删除通知时数据库错误: {e}")
            raise DALError(f"数据库错误：{e}") from e