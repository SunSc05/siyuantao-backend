import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient # 导入 TestClient
from app.main import app
import pyodbc
import asyncio
from uuid import uuid4 # 导入 uuid4
from app.dependencies import get_current_user, get_db_connection, get_order_service # 导入需要的依赖项
from unittest.mock import MagicMock # 导入 MagicMock
from app.services.order_service import OrderService # Import OrderService for type hinting
from unittest.mock import AsyncMock
import pytest_mock # Import pytest_mock

# 定义模拟用户 ID
TEST_USER_ID = uuid4()
TEST_SELLER_ID = uuid4() # Consider if these are needed here or in specific test fixtures
TEST_BUYER_ID = uuid4()

# Mock the OrderService dependency (moving from tests/order/test_orders_api.py)
@pytest.fixture
def mock_order_service(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Mock the OrderService dependency."""
    mock_service = AsyncMock(spec=OrderService)
    return mock_service

# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

@pytest.fixture(scope="function") # Changed scope to function for better test isolation
# 将异步 fixture 改为同步，并返回 TestClient
# Accept mock_order_service fixture
def client(mock_order_service: AsyncMock): # Add mock_order_service as a dependency
    # Override dependencies before creating the client
    # Override get_db_connection
    async def mock_get_db_connection():
        return MagicMock() # Return a mock connection object

    # Override get_order_service
    async def mock_get_order_service():
        return mock_order_service # Return the mocked service instance

    # Store original overrides to restore later
    original_get_current_user = app.dependency_overrides.get(get_current_user)
    original_get_db_connection = app.dependency_overrides.get(get_db_connection)
    original_get_order_service = app.dependency_overrides.get(get_order_service)

    # Apply overrides
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db_connection] = mock_get_db_connection
    app.dependency_overrides[get_order_service] = mock_get_order_service

    with TestClient(app=app) as client_instance:
        # 为测试目的添加一个模拟的用户ID
        client_instance.test_user_id = TEST_USER_ID # Keep test user ID accessible
        client_instance.test_seller_id = TEST_SELLER_ID # Keep test seller ID accessible
        client_instance.test_buyer_id = TEST_BUYER_ID # Keep test buyer ID accessible

        # 覆盖 get_current_user 依赖项
        async def mock_get_current_user():
            # This mock should return a dict that includes user_id, is_staff, is_verified, etc.
            # based on the expected payload from JWT decoding.
            # The actual user data (like is_staff, is_verified) can be controlled per test
            # by patching this mock or using different override context managers.
            return {"user_id": client_instance.test_user_id, "is_staff": False, "is_verified": True}

        # original_get_current_user = app.dependency_overrides.get(get_current_user)
        # app.dependency_overrides[get_current_user] = mock_get_current_user # This was already done above

        yield client_instance

        # 恢复原始依赖
        if original_get_current_user is not None:
            app.dependency_overrides[get_current_user] = original_get_current_user
        else:
            del app.dependency_overrides[get_current_user]

        if original_get_db_connection is not None:
             app.dependency_overrides[get_db_connection] = original_get_db_connection
        else:
             del app.dependency_overrides[get_db_connection]

        if original_get_order_service is not None:
             app.dependency_overrides[get_order_service] = original_get_order_service
        else:
             del app.dependency_overrides[get_order_service]

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