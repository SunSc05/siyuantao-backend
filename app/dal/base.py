# app/dal/base.py
import pyodbc
from app.exceptions import DALError, NotFoundError, IntegrityError, SQLSTATE_ERROR_MAP
from uuid import UUID
import logging
import asyncio # Import asyncio
import functools # Import functools
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- 通用查询执行器 ---
async def execute_query(
    conn: pyodbc.Connection,
    sql: str,
    params: tuple = None,
    fetchone: bool = False,
    fetchall: bool = False
) -> Optional[Dict[str, Any] | List[Dict[str, Any]] | int]:
    """
    通用 SQL 查询执行器。
    在线程池中异步执行同步数据库操作，将数据库结果转换为 Python 字典，并处理异常。
    :param conn: 数据库连接对象 (通过 FastAPI Depends 注入)
    :param sql: SQL 语句或存储过程调用字符串
    :param params: SQL 参数元组
    :param fetchone: 是否只获取一行结果 (返回 dict 或 None)
    :param fetchall: 是否获取所有结果 (返回 dict 列表)
    :return: 字典列表、单个字典、受影响的行数或 None
    """
    loop = asyncio.get_event_loop()

    # 在线程池中获取游标，因为 conn.cursor() 是阻塞的同步操作
    cursor = await loop.run_in_executor(None, conn.cursor)

    try:
        logger.debug(f"Executing SQL: {sql} with params: {params}")

        # 转换 UUID 对象为字符串，因为 pyodbc 可能不支持直接绑定 UUID 对象
        processed_params = tuple(str(p) if isinstance(p, UUID) else p for p in params) if params else None

        # 在线程池中执行 SQL 语句 (cursor.execute 是同步操作)
        if processed_params is not None:
            await loop.run_in_executor(None, functools.partial(cursor.execute, sql, processed_params))
        else:
            await loop.run_in_executor(None, functools.partial(cursor.execute, sql))

        if fetchone:
            # 在线程池中获取单行结果 (cursor.fetchone 是同步操作)
            row = await loop.run_in_executor(None, cursor.fetchone)
            if row:
                # 将 pyodbc Row 对象转换为字典
                columns = await loop.run_in_executor(None, lambda: [column[0] for column in cursor.description])
                result_dict = dict(zip(columns, row))
                return result_dict if result_dict else None # 返回字典或 None

            return None # No rows found

        elif fetchall:
            # 在线程池中获取所有结果 (cursor.fetchall 是同步操作)
            rows = await loop.run_in_executor(None, cursor.fetchall)
            if rows:
                columns = await loop.run_in_executor(None, lambda: [column[0] for column in cursor.description])
                results_list = []
                for row in rows:
                     result_dict = dict(zip(columns, row))
                     results_list.append(result_dict)
                return results_list

            return [] # Return empty list if no rows found

        else:
            # 对于 INSERT, UPDATE, DELETE 等非 SELECT 语句，返回受影响的行数
            # 在线程池中获取 rowcount (cursor.rowcount 是同步操作)
            rowcount = await loop.run_in_executor(None, lambda: cursor.rowcount)
            return rowcount # 返回受影响的行数


    except pyodbc.Error as e:
        # 根据 pyodbc 错误信息判断并抛出自定义异常
        error_message = str(e)
        # 重新评估错误信息的匹配逻辑，确保能捕捉到存储过程中的 RAISERROR 消息
        # 注意：这里需要根据您的 SQL Server 配置和驱动，确定 RAISERROR 消息如何体现在 pyodbc.Error 中
        # 如果简单的字符串匹配不够，可能需要解析更详细的错误信息（如 SQLSTATE 或 Native Error Code）
        # 目前先保留基于字符串的匹配，但这可能是潜在的不稳定性来源
        if '用户不存在' in error_message or '找不到' in error_message:
             raise NotFoundError(error_message) from e
        elif '已存在' in error_message or '重复' in error_message:
             raise IntegrityError(error_message) from e
        elif '无权限' in error_message or '管理员' in error_message:
             raise ForbiddenError(error_message) from e
        elif '无效的' in error_message or '必须提供' in error_message:
             raise DALError(error_message) from e # 映射为 DALError
        else:
             logger.error(f"Database error executing SQL: {sql} - {e}")
             raise DALError(f"Database operation failed: {e}") from e

    except Exception as e:
        # 捕获其他意外异常
        logger.error(f"Unexpected error executing SQL: {sql} - {e}")
        raise DALError(f"An unexpected database error occurred: {e}") from e

    finally:
        # 在线程池中关闭游标 (cursor.close 是同步操作)
        # 确保游标对象存在且可关闭
        if 'cursor' in locals() and cursor:
             await loop.run_in_executor(None, cursor.close)
        # 注意：连接不在此处关闭，由依赖注入管理其生命周期

        
# TODO: Transaction context manager might also need similar async/sync handling

# 事务上下文管理器 (可选但推荐，用于涉及多个 DAL 操作的原子性)
# async with transaction(conn):
#     await dal_op1(conn)
#     await dal_op2(conn)
from contextlib import asynccontextmanager
def transaction(conn: pyodbc.Connection):
    @asynccontextmanager
    async def _transaction_context():
        try:
            yield conn
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
        except Exception as e:
            await asyncio.get_event_loop().run_in_executor(None, conn.rollback)
            raise
    return _transaction_context()