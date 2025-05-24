# app/dal/users.py
import pyodbc
from app.dal.base import execute_query
from app.exceptions import NotFoundError, IntegrityError, DALError
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

async def get_user_by_id(conn: pyodbc.Connection, user_id: UUID) -> dict | None:
    """从数据库获取指定 ID 的用户。"""
    sql = "{CALL sp_GetUserByID(?)}" # 假设存储过程
    result = await execute_query(conn, sql, (user_id,), fetchone=True)
    return result

async def get_user_by_username(conn: pyodbc.Connection, username: str) -> dict | None:
    """从数据库获取指定用户名的用户。"""
    sql = "{CALL sp_GetUserByUsername(?)}"
    result = await execute_query(conn, sql, (username,), fetchone=True)
    return result

async def create_user(conn: pyodbc.Connection, username: str, email: str, hashed_password: str) -> dict:
    """在数据库中创建新用户并返回其数据。"""
    try:
        sql = "{CALL sp_CreateUser(?, ?, ?)}" # 假设存储过程返回新用户的所有字段
        # 注意：如果 sp_CreateUser 返回的 user_id 不是 UUID 类型，这里需要处理
        result = await execute_query(conn, sql, (username, email, hashed_password), fetchone=True)
        if not result:
            raise DALError("User creation failed: No data returned from stored procedure.")
        return result
    except IntegrityError as e:
        # 根据存储过程的错误信息或 SQLSTATE 进一步区分错误
        if "duplicate key" in e.message.lower() and "username" in e.message.lower():
            raise IntegrityError("Username already exists.")
        if "duplicate key" in e.message.lower() and "email" in e.message.lower():
            raise IntegrityError("Email already exists.")
        raise # 重新抛出其他完整性错误

async def update_user(conn: pyodbc.Connection, user_id: UUID, username: str = None, email: str = None, hashed_password: str = None) -> dict | None:
    """更新用户信息。"""
    sql = "{CALL sp_UpdateUser(?, ?, ?, ?)}"
    # 仅传递非 None 的参数，具体取决于存储过程的设计
    result = await execute_query(conn, sql, (user_id, username, email, hashed_password), fetchone=True)
    if not result:
        raise NotFoundError(f"User with ID {user_id} not found for update.")
    return result

async def delete_user(conn: pyodbc.Connection, user_id: UUID) -> int:
    """删除用户。返回影响行数。"""
    sql = "{CALL sp_DeleteUser(?)}"
    row_count = await execute_query(conn, sql, (user_id,))
    if row_count == 0:
        raise NotFoundError(f"User with ID {user_id} not found for deletion.")
    return row_count