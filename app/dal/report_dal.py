import pyodbc
from app.dal.base import execute_query  # 假设 base.py 提供通用查询执行函数
from app.exceptions import NotFoundError, DALError, ForbiddenError
from uuid import UUID
import logging
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger(__name__)


class ReportDAL:
    def __init__(self, execute_query_func):
        """
        初始化 ReportDAL，依赖注入数据库查询执行函数
        :param execute_query_func: 执行数据库查询的函数（通常由 Service 层注入）
        """
        self.execute_query_func = execute_query_func

    async def create_report(
        self,
        conn: pyodbc.Connection,
        reporter_user_id: UUID,
        report_content: str, 
        reported_user_id: Optional[UUID] = None,
        reported_product_id: Optional[UUID] = None,
        reported_order_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        提交举报（封装 sp_CreateReport）
        :param conn: 数据库连接对象
        :param reporter_user_id: 举报者用户ID
        :param reported_user_id: 被举报用户ID（可选）
        :param reported_product_id: 被举报商品ID（可选）
        :param reported_order_id: 被举报订单ID（可选）
        :param report_content: 举报内容
        :return: 包含 NewReportID 的结果字典
        """
        logger.debug(f"DAL: 尝试提交举报，举报者ID: {reporter_user_id}")
        sql = "{CALL sp_CreateReport(?, ?, ?, ?, ?)}"
        params = (
            reporter_user_id,
            reported_user_id,
            reported_product_id,
            reported_order_id,
            report_content
        )

        try:
            result = await self.execute_query_func(conn, sql, params, fetchone=True)
            logger.debug(f"DAL: sp_CreateReport 返回结果: {result}")

            if not result or not isinstance(result, dict):
                raise DALError("提交举报时返回无效结果")

            # 检查存储过程返回的错误信息
            if "错误" in result or "Error" in result:
                error_msg = result.get("错误") or result.get("Error")
                if "举报者用户不存在" in error_msg:
                    raise NotFoundError("举报者用户不存在")
                if "举报内容不能为空" in error_msg:
                    raise DALError("举报内容不能为空")
                if "被举报用户不存在" in error_msg:
                    raise NotFoundError("被举报用户不存在")
                if "被举报商品不存在" in error_msg:
                    raise NotFoundError("被举报商品不存在")
                if "被举报订单不存在" in error_msg:
                    raise NotFoundError("被举报订单不存在")
                raise DALError(f"存储过程错误: {error_msg}")

            # 验证 NewReportID 有效性
            new_report_id = result.get("NewReportID")
            if not new_report_id:
                raise DALError("提交举报后未返回新举报ID")
            try:
                UUID(str(new_report_id))  # 验证是否为有效 UUID
            except ValueError:
                raise DALError(f"返回的 NewReportID 格式无效: {new_report_id}")

            return result

        except pyodbc.Error as e:
            logger.error(f"DAL: 提交举报时发生数据库错误: {e}")
            raise DALError(f"数据库错误: {e}") from e

    async def get_report_list(
        self,
        conn: pyodbc.Connection,
        status: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取举报列表（封装 sp_GetReportList）
        :param conn: 数据库连接对象
        :param status: 举报状态（可选，值为 'Pending', 'Resolved', 'Rejected'）
        :param page_number: 页码（从1开始）
        :param page_size: 每页数量
        :return: （举报列表, 总记录数）
        """
        logger.debug(f"DAL: 尝试获取举报列表，状态: {status}, 页码: {page_number}, 每页数量: {page_size}")
        sql = "{CALL sp_GetReportList(?, ?, ?)}"
        params = (status, page_number, page_size)

        try:
            result = await self.execute_query_func(conn, sql, params, fetchall=True)
            logger.debug(f"DAL: sp_GetReportList 返回结果数量: {len(result)}")

            if not result:
                return [], 0

            # 提取总记录数（所有行的总记录数相同）
            total_count = result[0].get("总记录数", 0)
            # 过滤掉总记录数字段，仅保留举报数据
            report_list = [{k: v for k, v in item.items() if k != "总记录数"} for item in result]
            return report_list, total_count

        except pyodbc.Error as e:
            logger.error(f"DAL: 获取举报列表时发生数据库错误: {e}")
            raise DALError(f"数据库错误: {e}") from e

    async def handle_report(
        self,
        conn: pyodbc.Connection,
        report_id: UUID,
        admin_id: UUID,
        new_status: str,
        processing_result: str
    ) -> Dict[str, str]:
        """
        处理举报（封装 sp_HandleReport）
        :param conn: 数据库连接对象
        :param report_id: 举报ID
        :param admin_id: 处理管理员ID
        :param new_status: 新状态（'Resolved'/'Rejected'）
        :param processing_result: 处理结果描述
        :return: 操作结果字典
        """
        logger.debug(f"DAL: 尝试处理举报，举报ID: {report_id}, 管理员ID: {admin_id}")
        sql = "{CALL sp_HandleReport(?, ?, ?, ?)}"
        params = (report_id, admin_id, new_status, processing_result)

        try:
            result = await self.execute_query_func(conn, sql, params, fetchone=True)
            logger.debug(f"DAL: sp_HandleReport 返回结果: {result}")

            if not result or not isinstance(result, dict):
                raise DALError("处理举报时返回无效结果")

            # 检查存储过程返回的错误信息
            if "错误" in result or "Error" in result:
                error_msg = result.get("错误") or result.get("Error")
                if "管理员不存在或无权限" in error_msg:
                    raise ForbiddenError("管理员无权限处理举报")
                if "举报不存在" in error_msg:
                    raise NotFoundError("举报不存在")
                if "举报状态非待处理" in error_msg:
                    raise DALError("举报状态非待处理，无法重复处理")
                if "无效的处理状态" in error_msg:
                    raise DALError("无效的处理状态，仅允许 'Resolved' 或 'Rejected'")
                if "处理结果描述不能为空" in error_msg:
                    raise DALError("处理结果描述不能为空")
                raise DALError(f"存储过程错误: {error_msg}")

            return result

        except pyodbc.Error as e:
            logger.error(f"DAL: 处理举报时发生数据库错误: {e}")
            raise DALError(f"数据库错误: {e}") from e