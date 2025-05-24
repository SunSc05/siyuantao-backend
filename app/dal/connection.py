# app/dal/connection.py
from app.exceptions import DALError

import pyodbc
from app.config import get_connection_string
import logging

logger = logging.getLogger(__name__)

# 使用 FastAPI 的依赖注入风格，为每个请求提供一个连接
async def get_db_connection():
    """
    依赖注入函数，提供一个 pyodbc 数据库连接。
    确保连接在请求结束时关闭。
    """
    conn = None
    try:
        conn_str = get_connection_string()
        # autocommit=False 允许手动管理事务
        conn = pyodbc.connect(conn_str, autocommit=False)
        logger.debug("Database connection established.")
        yield conn # 将连接提供给依赖它的函数
    except pyodbc.Error as ex:
        # 捕获连接错误，记录并重新抛出更通用的 DALError
        sqlstate = ex.args[0]
        error_message = ex.args[1]
        logger.error(f"Database connection error: {sqlstate} - {error_message}")
        raise DALError(f"Failed to connect to database: {error_message}") from ex
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed.") 