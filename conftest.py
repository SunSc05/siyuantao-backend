import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient # 导入 TestClient
from app.main import app
import pyodbc
import asyncio
from uuid import uuid4 # 导入 uuid4
from app.dependencies import get_current_user # 导入 get_current_user

# 定义模拟用户 ID
TEST_USER_ID = uuid4()
TEST_SELLER_ID = uuid4()
TEST_BUYER_ID = uuid4()

# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

@pytest.fixture(scope="session")
# 将异步 fixture 改为同步，并返回 TestClient
def client():
    with TestClient(app=app) as client_instance:
        # 为测试目的添加一个模拟的用户ID
        client_instance.test_user_id = TEST_USER_ID

        # 覆盖 get_current_user 依赖项
        async def mock_get_current_user():
            return {"user_id": client_instance.test_user_id, "is_staff": False, "is_verified": True}

        original_get_current_user = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = mock_get_current_user

        yield client_instance

        # 恢复原始依赖
        if original_get_current_user is not None:
            app.dependency_overrides[get_current_user] = original_get_current_user
        else:
            del app.dependency_overrides[get_current_user]

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