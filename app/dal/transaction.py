import pyodbc
import asyncio
from contextlib import asynccontextmanager
from app.exceptions import DALError
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def transaction(conn: pyodbc.Connection):
    """
    一个异步上下文管理器，用于管理数据库事务。
    在进入上下文时，确保连接处于手动提交模式。
    在成功退出上下文时提交事务。
    在发生异常时回滚事务。
    """
    try:
        # Ensure the connection is in manual commit mode if it's from a pool and autocommit is enabled by default
        # For PooledDB connections, conn.autocommit should be False by default, but it's good to be explicit.
        if conn.autocommit:
            conn.autocommit = False

        yield conn
        logger.debug("Transaction: Committing changes.")
        # Use asyncio.to_thread for blocking commit operation
        await asyncio.to_thread(conn.commit)
    except Exception as e:
        logger.error(f"Transaction: Rolling back changes due to error: {e}", exc_info=True)
        # Use asyncio.to_thread for blocking rollback operation
        if conn:
            await asyncio.to_thread(conn.rollback)
 