import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient # 导入 TestClient
from app.main import app
import pyodbc
import asyncio
from uuid import uuid4 # 导入 uuid4
from app.dependencies import get_current_user, get_db_connection, get_order_service, get_evaluation_service # 导入需要的依赖项
from unittest.mock import MagicMock # 导入 MagicMock
from app.services.order_service import OrderService # Import OrderService for type hinting
from app.services.evaluation_service import EvaluationService # Import EvaluationService for type hinting
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

# Mock the EvaluationService dependency (moving from tests/evaluation/test_evaluation_api.py)
@pytest.fixture
def mock_evaluation_service(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return AsyncMock(spec=EvaluationService)

# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

@pytest.fixture(scope="function") # Changed scope to function for better test isolation
# 将异步 fixture 改为同步，并返回 TestClient
# Accept mock_order_service fixture
def client(mock_order_service: AsyncMock, mock_evaluation_service: AsyncMock, mock_db_connection: MagicMock, mocker: pytest_mock.MockerFixture): # Add mock_evaluation_service, mock_db_connection
    # Override dependencies before creating the client

    # No need to patch app.config.settings here, it's handled globally by mock_global_settings_class

    # Override get_db_connection
    async def override_get_db_connection_async():
        # Return a mock connection object
        return mock_db_connection # Use the shared mock_db_connection fixture

    # Override get_order_service
    async def mock_get_order_service():
        return mock_order_service

    # Override get_evaluation_service
    async def mock_get_evaluation_service():
        return mock_evaluation_service

    # Mock get_current_user to return a fixed test user
    async def mock_get_current_user_override():
        # This will be the 'current_user' in the router
        # Return a dict that matches the expected payload structure
        # Use a consistent test user ID (UUID)
        return {"user_id": str(client.test_user_id), "is_staff": False, "is_verified": True}

    app.dependency_overrides[get_db_connection] = override_get_db_connection_async
    app.dependency_overrides[get_order_service] = mock_get_order_service
    app.dependency_overrides[get_evaluation_service] = mock_get_evaluation_service
    app.dependency_overrides[get_current_user] = mock_get_current_user_override

    # Create the TestClient with overridden dependencies
    with TestClient(app) as client:
        client.test_user_id = uuid4() # Assign a test user ID to the client instance
        yield client
    app.dependency_overrides.clear() # Clean up overrides after test