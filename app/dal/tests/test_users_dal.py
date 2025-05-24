# app/dal/tests/test_users_dal.py
import pytest
import pyodbc
from uuid import uuid4, UUID
from app.dal.users import create_user, get_user_by_id, get_user_by_username, update_user, delete_user
from app.dal.connection import get_connection_string
from app.exceptions import NotFoundError, IntegrityError, DALError
import asyncio # For explicit async calls

# 配置测试数据库连接字符串 (可以从环境变量或单独的测试配置文件获取)
TEST_DB_CONN_STR = get_connection_string() # 确保连接到测试数据库！

@pytest.fixture(scope="function", autouse=True)
async def db_conn_fixture():
    """为每个测试函数提供一个独立的数据库连接，并在测试结束后回滚事务。"""
    conn = pyodbc.connect(TEST_DB_CONN_STR, autocommit=False)
    try:
        yield conn
        conn.rollback() # 确保测试不影响其他测试
    finally:
        conn.close()

# 辅助函数：清理测试数据 (如果需要，例如在每个测试前清空表)
async def _clean_users_table(conn: pyodbc.Connection):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Users;") # 清空表
    conn.commit()
    cursor.close()

@pytest.mark.asyncio
async def test_create_and_get_user(db_conn_fixture: pyodbc.Connection):
    await _clean_users_table(db_conn_fixture) # 确保测试环境干净
    username = "testuser_dal"
    email = "test_dal@example.com"
    password_hash = "hashed_password"

    # 创建用户
    created_user = await create_user(db_conn_fixture, username, email, password_hash)
    assert created_user is not None
    assert isinstance(created_user['user_id'], UUID)
    assert created_user['username'] == username
    assert created_user['email'] == email

    # 获取用户
    retrieved_user = await get_user_by_id(db_conn_fixture, created_user['user_id'])
    assert retrieved_user is not None
    assert retrieved_user['user_id'] == created_user['user_id']
    assert retrieved_user['username'] == username

    retrieved_user_by_name = await get_user_by_username(db_conn_fixture, username)
    assert retrieved_user_by_name is not None
    assert retrieved_user_by_name['username'] == username

@pytest.mark.asyncio
async def test_create_user_duplicate_username(db_conn_fixture: pyodbc.Connection):
    await _clean_users_table(db_conn_fixture)
    username = "duplicate_name"
    email1 = "email1@example.com"
    email2 = "email2@example.com"
    password = "password"

    await create_user(db_conn_fixture, username, email1, password)

    with pytest.raises(IntegrityError, match="Username already exists."):
        await create_user(db_conn_fixture, username, email2, password)

@pytest.mark.asyncio
async def test_update_user(db_conn_fixture: pyodbc.Connection):
    await _clean_users_table(db_conn_fixture)
    user_id = uuid4()
    await create_user(db_conn_fixture, "original", "original@example.com", "pass")

    updated_user = await update_user(db_conn_fixture, user_id, username="updated_name")
    assert updated_user['username'] == "updated_name"

    # Test update non-existent user
    with pytest.raises(NotFoundError):
        await update_user(db_conn_fixture, uuid4(), username="nonexistent")

@pytest.mark.asyncio
async def test_delete_user(db_conn_fixture: pyodbc.Connection):
    await _clean_users_table(db_conn_fixture)
    user_id = uuid4()
    await create_user(db_conn_fixture, "to_delete", "delete@example.com", "pass")

    deleted_count = await delete_user(db_conn_fixture, user_id)
    assert deleted_count == 1

    with pytest.raises(NotFoundError):
        await get_user_by_id(db_conn_fixture, user_id)

    # Test delete non-existent user
    with pytest.raises(NotFoundError):
        await delete_user(db_conn_fixture, uuid4())