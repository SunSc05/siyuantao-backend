import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock
from fastapi import Depends, status, HTTPException
import pytest_mock
from app.dal.connection import get_db_connection
from app.dependencies import get_current_user, get_current_active_admin_user, get_current_active_admin_user as get_current_active_admin_user_dependency, get_current_user as get_current_user_dependency
from app.main import app
from app.services.report_service import ReportService
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError

# --- Mock settings fixture to avoid validation errors --- (New)
@pytest.fixture(scope="function")
def mock_settings(mocker):
    mock = mocker.MagicMock()
    mock.DATABASE_SERVER = "mock_server"
    mock.DATABASE_NAME = "mock_db"
    mock.DATABASE_UID = "mock_uid"
    mock.DATABASE_PWD = "mock_pwd"
    mock.SECRET_KEY = "mock_secret_key"
    mock.ALGORITHM = "HS256"
    mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock.EMAIL_PROVIDER = "smtp"
    mock.SENDER_EMAIL = "test@example.com"
    mock.FRONTEND_DOMAIN = "http://localhost:3301"
    mock.MAGIC_LINK_EXPIRE_MINUTES = 15
    mock.ODBC_DRIVER = "ODBC Driver 17 for SQL Server"
    mock.ALIYUN_EMAIL_ACCESS_KEY_ID = "mock_aliyun_id"
    mock.ALIYUN_EMAIL_ACCESS_KEY_SECRET = "mock_aliyun_secret"
    mock.ALIYUN_EMAIL_REGION = "cn-hangzhou"
    return mock

# --- Mock Authentication Dependencies using dependency_overrides ---
# Define Mock functions to be used with dependency_overrides
async def mock_get_current_user_override():
    test_user_id = UUID("12345678-1234-5678-1234-567812345678")
    return {"user_id": test_user_id, "UserID": test_user_id, "username": "testuser", "is_staff": False, "is_verified": True}

async def mock_get_current_active_admin_user_override():
    test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000")
    return {"user_id": test_admin_user_id, "UserID": test_admin_user_id, "username": "adminuser", "is_staff": True, "is_verified": True}

@pytest.fixture(scope="function")
def client(mock_report_service, mocker, mock_settings):
    mocker.patch('app.config.settings', new=mock_settings)

    async def override_get_db_connection_async():
        mock_conn = MagicMock()
        yield mock_conn

    app.dependency_overrides[get_db_connection] = override_get_db_connection_async
    app.dependency_overrides[get_current_user_dependency] = mock_get_current_user_override
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_override
    app.dependency_overrides[lambda: ReportService()] = lambda: mock_report_service

    with TestClient(app) as tc:
        tc.test_user_id = UUID("12345678-1234-5678-1234-567812345678")
        tc.test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000")
        yield tc

    app.dependency_overrides.clear()

@pytest.fixture
def mock_report_service(mocker):
    mock_service = AsyncMock(spec=ReportService)
    return mock_service

# 测试创建举报接口
@pytest.mark.anyio
async def test_create_report(client: TestClient, mock_report_service: AsyncMock):
    # 模拟服务层返回结果
    mock_result = {"message": "举报创建成功"}
    mock_report_service.create_report.return_value = mock_result

    # 发送请求
    response = client.post("/api/v1/reports/")

    # 断言响应状态码和内容
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == mock_result

    # 验证服务方法是否被调用
    mock_report_service.create_report.assert_called_once()

# 测试管理员获取举报列表接口
@pytest.mark.anyio
async def test_get_reports(client: TestClient, mock_report_service: AsyncMock):
    # 模拟服务层返回结果
    mock_reports = [{"id": 1, "content": "举报内容"}]
    mock_report_service.get_reports.return_value = mock_reports

    # 发送请求
    response = client.get("/api/v1/reports/admin")

    # 断言响应状态码和内容
    assert response.status_code == 200
    assert response.json() == mock_reports

    # 验证服务方法是否被调用
    mock_report_service.get_reports.assert_called_once()

# 测试管理员处理举报接口
@pytest.mark.anyio
async def test_handle_report(client: TestClient, mock_report_service: AsyncMock):
    report_id = uuid4()

    # 发送请求
    response = client.put(f"/api/v1/reports/{report_id}/admin/handle")

    # 断言响应状态码
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # 验证服务方法是否被调用
    mock_report_service.handle_report.assert_called_once()