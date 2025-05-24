import pytest
from httpx import AsyncClient
from app.main import app
import pyodbc
import asyncio

# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

# @pytest.fixture(scope="session")
# async def client():
#     async with AsyncClient(app=app, base_url="http://test") as ac:
#         yield ac

# Remove the clean_db fixture as we are mocking the DAL/Service
# @pytest.fixture(scope="function", autouse=True)
# async def clean_db():
# ... removed ...

# TODO: Add more用于生成测试数据的 fixtures (如创建测试用户、测试商品等)
# @pytest.fixture
# def test_user(client): # 或者接受 db_conn_fixture
#     # 在测试数据库中创建测试用户
#     user_data = {...}
#     # 调用 sp_CreateUser 存储过程 或 API endpoint
#     # 返回创建的用户对象或ID
#     pass

# @pytest.fixture
# def test_product(test_user): # 依赖 test_user fixture
#     # 在测试数据库中创建测试商品，并关联到 test_user
#     # 调用 sp_CreateProduct 存储过程 或 API endpoint
#     # 返回创建的商品对象或ID
#     pass 