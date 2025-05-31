# app/dal/connection.py
from app.exceptions import DALError

import pyodbc
from app.config import settings # Re-import settings to get connection string components
import logging
import asyncio # Keep asyncio for `to_thread` if we wrap `pyodbc.connect`
from app.dal.transaction import transaction # Keep the transaction context manager
# from app.core.db import get_pooled_connection # Comment out or remove
from fastapi import Request # Keep Request for dependency injection

logger = logging.getLogger(__name__)

# 使用 FastAPI 的依赖注入风格，为每个请求提供一个连接
async def get_db_connection(request: Request): # Keep request: Request parameter
    """
    依赖注入函数，提供一个 pyodbc 数据库连接，并在请求结束时管理事务和关闭连接。
    """
    conn = None
    try:
        # Revert to direct pyodbc.connect
        conn_str = (
            f"DRIVER={{{settings.ODBC_DRIVER}}};"
            f"SERVER={settings.DATABASE_SERVER};"
            f"DATABASE={settings.DATABASE_NAME};"
            f"UID={settings.DATABASE_UID};"
            f"PWD={settings.DATABASE_PWD}"
        )
        # Use asyncio.to_thread for blocking pyodbc.connect
        conn = await asyncio.to_thread(lambda: pyodbc.connect(conn_str, autocommit=False))
        request.state.db_connection = conn # Store connection in request state (optional, for debugging)
        logger.debug("Database connection established (direct connect).")

        # Use the transaction context manager to handle commit/rollback
        async with transaction(conn) as trans_conn:
            yield trans_conn # Provide the connection to dependent functions
        # The transaction context manager handles commit/rollback upon exiting this block

    except DALError as e:
        logger.error(f"Database connection/transaction error: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred during database operation: {e}", exc_info=True)
        raise DALError(f"服务器内部错误: {e}") from e
    finally:
        # Ensure the connection is closed
        if conn:
            await asyncio.to_thread(conn.close)
            logger.debug("Database connection closed (direct connect).") 