# tests/conftest.py (共享的测试 fixtures)
import pytest
from httpx import AsyncClient
import pyodbc
from app.main import app
from app.config import get_connection_string

TEST_DB_CONN_STR = get_connection_string() # 确保指向测试数据库

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="function")
async def client():
    """为每个测试提供一个 FastAPI 测试客户端"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db_after_test():
    """每个测试函数执行后清理数据库，确保测试隔离。"""
    conn = pyodbc.connect(TEST_DB_CONN_STR, autocommit=True)
    cursor = conn.cursor()
    try:
        yield
    finally:
        # 清理所有受影响的表 (根据您的模块和外键关系调整顺序)
        # 注意：这里的表名 Users 需要根据您的实际 SQL 定义来确定
        cursor.execute("DELETE FROM Users;")
        # cursor.execute("DELETE FROM OrderItems;")
        # cursor.execute("DELETE FROM Orders;")
        # cursor.execute("DELETE FROM Products;")
        conn.commit()
        cursor.close()
        conn.close() 