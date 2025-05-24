# app/dal/base.py
import pyodbc
from app.exceptions import DALError, NotFoundError, IntegrityError, SQLSTATE_ERROR_MAP
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

async def execute_query(
    conn: pyodbc.Connection,
    sql: str,
    params: tuple = None,
    fetchone: bool = False,
    fetchall: bool = False
):
    """
    通用 SQL 查询执行器。
    将数据库结果转换为 Python 字典，并处理异常。
    :param conn: 数据库连接对象 (通过 FastAPI Depends 注入)
    :param sql: SQL 语句或存储过程调用字符串
    :param params: SQL 参数元组
    :param fetchone: 是否只获取一行结果 (返回 dict 或 None)
    :param fetchall: 是否获取所有结果 (返回 dict 列表)
    :return: 字典列表、单个字典或 None
    """
    cursor = conn.cursor()
    try:
        logger.debug(f"Executing SQL: {sql} with params: {params}")

        # 转换 UUID 对象为字符串，因为 pyodbc 可能不支持直接绑定 UUID 对象
        # 注意：某些版本的 pyodbc 可能支持直接绑定 UUID，但统一转换为字符串更保险
        processed_params = tuple(str(p) if isinstance(p, UUID) else p for p in params) if params else None

        cursor.execute(sql, processed_params)

        if fetchone or fetchall:
            columns = [column[0] for column in cursor.description]
            if fetchone:
                row = cursor.fetchone()
                # 尝试将 UUID 字符串转换回 UUID 对象
                if row:
                    result = dict(zip(columns, row))
                    for key, value in result.items():
                        if isinstance(value, str):
                            try: # 假设所有 GUID 字段在数据库中存储为 UNIQUEIDENTIFIER
                                # 尝试将其转换为 UUID 对象，如果失败则保持原样
                                if len(value) == 36 and '-' in value: # 简单的 UUID 格式检查
                                    result[key] = UUID(value)
                            except ValueError:
                                pass # 不是有效的 UUID string
                    return result
                return None
            else:
                rows = cursor.fetchall()
                result_list = []
                for row in rows:
                    item = dict(zip(columns, row))
                    for key, value in item.items():
                        if isinstance(value, str):
                            try:
                                if len(value) == 36 and '-' in value:
                                    item[key] = UUID(value)
                            except ValueError:
                                pass
                    result_list.append(item)
                return result_list
        else:
            # 对于非 SELECT 操作 (INSERT, UPDATE, DELETE)，提交事务
            conn.commit()
            return cursor.rowcount # 返回影响行数

    except pyodbc.Error as ex:
        conn.rollback() # 发生错误时回滚事务
        sqlstate = ex.args[0]
        error_message = ex.args[1]
        logger.error(f"SQL Error: {sqlstate} - {error_message} for query: {sql} with params: {params}")

        # 映射到自定义异常
        if sqlstate in SQLSTATE_ERROR_MAP:
            raise SQLSTATE_ERROR_MAP[sqlstate](error_message)
        else:
            raise DALError(error_message) from ex # 抛出通用 DAL 错误

    finally:
        cursor.close()

# 事务上下文管理器 (可选但推荐，用于涉及多个 DAL 操作的原子性)
# async with transaction(conn):
#     await dal_op1(conn)
#     await dal_op2(conn)
# def transaction(conn: pyodbc.Connection):
#     @asynccontextmanager
#     async def _transaction_context():
#         try:
#             yield conn
#             conn.commit()
#         except Exception as e:
#             conn.rollback()
#             raise
#     return _transaction_context() 