# app/dal/connection.py
from app.exceptions import DALError

import pyodbc
from app.config import get_connection_string
import logging
# Import the transaction context manager
from app.dal.base import transaction # Assuming transaction is in base.py

logger = logging.getLogger(__name__)

# 使用 FastAPI 的依赖注入风格，为每个请求提供一个连接
async def get_db_connection():
    """
    依赖注入函数，提供一个 pyodbc 数据库连接，并在请求结束时管理事务和关闭连接。
    """
    logger.debug("Attempting to get database connection.")
    conn = None
    try:
        conn_str = get_connection_string()
        # autocommit=False 允许手动管理事务，这正是我们需要 transaction 上下管理器来做的
        conn = pyodbc.connect(conn_str, autocommit=False)
        logger.debug("Database connection established.")
        
        # Use the transaction context manager to handle commit/rollback
        async with transaction(conn) as trans_conn:
             yield trans_conn # 将连接提供给依赖它的函数
        # The transaction context manager handles commit/rollback upon exiting this block
        
        logger.debug("Database connection yielding connection (transaction managed).")
    except pyodbc.Error as ex:
        # 捕获连接错误，记录并重新抛出更通用的 DALError
        sqlstate = ex.args[0]
        error_message = ex.args[1]
        logger.error(f"Database connection error: {sqlstate} - {error_message}")
        # Note: Transaction context manager handles rollback on exceptions *after* yield.
        # This catch block is primarily for connection *establishment* errors.
        raise DALError(f"Failed to connect to database: {error_message}") from ex
    finally:
        # Ensure the connection is closed even if transaction context manager failed or connection wasn't established
        if conn:
            conn.close()
            logger.debug("Database connection closed.") 