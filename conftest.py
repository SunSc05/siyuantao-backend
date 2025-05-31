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
from fastapi import Depends
from app.dependencies import get_user_service as get_user_service_dependency
from app.services.user_service import UserService # Import UserService
from app.config import Settings # Import Settings class
import os # Import os for patching environment variables
from uuid import UUID

# 定义模拟用户 ID
TEST_USER_ID = UUID("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11") # 示例用户ID
TEST_SELLER_ID = UUID("b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12") # 示例卖家ID
TEST_BUYER_ID = UUID("c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13") # 示例买家ID
TEST_ADMIN_USER_ID = UUID("d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14") # 示例管理员ID

# --- Global Mock for Settings Class (autouse) ---
@pytest.fixture(autouse=True, scope="function") # Changed scope to function
def mock_global_settings_class(mocker):
    """Globally mocks the Settings class to prevent ValidationError on import."""
    # Patch the Settings class directly to return a MagicMock instance when instantiated
    mock_settings_instance = MagicMock(spec=Settings)

    # Configure the mock settings instance with default values
    mock_settings_instance.DATABASE_SERVER = "mock_server"
    mock_settings_instance.DATABASE_NAME = "mock_db"
    mock_settings_instance.DATABASE_UID = "mock_uid"
    mock_settings_instance.DATABASE_PWD = "mock_pwd"
    mock_settings_instance.SECRET_KEY = "mock_secret_key"
    mock_settings_instance.ALGORITHM = "HS256"
    mock_settings_instance.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock_settings_instance.EMAIL_PROVIDER = "smtp"
    mock_settings_instance.SENDER_EMAIL = "test@example.com"
    mock_settings_instance.FRONTEND_DOMAIN = "http://localhost:3301"
    mock_settings_instance.MAGIC_LINK_EXPIRE_MINUTES = 15
    mock_settings_instance.ODBC_DRIVER = "ODBC Driver 17 for SQL Server"
    mock_settings_instance.ALIYUN_EMAIL_ACCESS_KEY_ID = "mock_aliyun_id"
    mock_settings_instance.ALIYUN_EMAIL_ACCESS_KEY_SECRET = "mock_aliyun_secret"
    mock_settings_instance.ALIYUN_EMAIL_REGION = "cn-hangzhou"

    # When app.config.Settings() is called, it will return this mock instance
    mocker.patch('app.config.Settings', return_value=mock_settings_instance)

    # Yield the mock instance for other fixtures/tests to use if needed (though autouse means it's always active)
    yield mock_settings_instance

# Mock the OrderService dependency (moving from tests/order/test_orders_api.py)
@pytest.fixture
def mock_order_service(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return AsyncMock(spec=OrderService)

# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

@pytest.fixture(scope="function") # Changed scope to function for better test isolation
# 将异步 fixture 改为同步，并返回 TestClient
# Accept mock_order_service fixture
def client(mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture): # Removed mock_settings from args
    # Override dependencies before creating the client

    # No need to patch app.config.settings here, it's handled globally by mock_global_settings_class

    # Override get_db_connection
    async def mock_get_db_connection():
        mock_conn = MagicMock()
        yield mock_conn

    # Override get_order_service
    async def mock_get_order_service():
        return mock_order_service

    app.dependency_overrides[get_db_connection] = mock_get_db_connection
    app.dependency_overrides[get_order_service_dependency] = mock_get_order_service
    app.dependency_overrides[get_user_service_dependency] = AsyncMock(spec=UserService) # Provide a default mock for UserService

    with TestClient(app) as tc:
        # 为测试目的添加一个模拟的用户ID
        tc.test_user_id = TEST_USER_ID # Keep test user ID accessible
        tc.test_seller_id = TEST_SELLER_ID # Keep test seller ID accessible
        tc.test_buyer_id = TEST_BUYER_ID # Keep test buyer ID accessible
        yield tc

    # Clear overrides after the test
    app.dependency_overrides.clear()