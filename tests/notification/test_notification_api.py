import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock
import pytest_mock
from app.dal.connection import get_db_connection
from app.dependencies import get_current_user, get_current_active_admin_user, get_user_service
from app.main import app
from app.services.system_notification_service import SystemNotificationService

# --- Mock Authentication Dependencies using dependency_overrides ---
async def mock_get_current_user_override():
    test_user_id = UUID("12345678-1234-5678-1234-567812345678")
    return {"user_id": test_user_id, "UserID": test_user_id, "username": "testuser", "is_staff": False, "is_verified": True}

async def mock_get_current_active_admin_user_override():
    test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000")
    return {"user_id": test_admin_user_id, "UserID": test_admin_user_id, "username": "adminuser", "is_staff": True, "is_verified": True}

@pytest.fixture(scope="function")
def client(mock_user_service, mocker):
    async def override_get_db_connection_async():
        mock_conn = MagicMock()
        yield mock_conn

    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[get_db_connection] = override_get_db_connection_async
    app.dependency_overrides[get_current_user] = mock_get_current_user_override
    app.dependency_overrides[get_current_active_admin_user] = mock_get_current_active_admin_user_override

    with TestClient(app) as tc:
        tc.test_user_id = UUID("12345678-1234-5678-1234-567812345678")
        tc.test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000")
        yield tc

    app.dependency_overrides.clear()

@pytest.fixture
def mock_user_service(mocker):
    mock_service = AsyncMock(spec=SystemNotificationService)
    return mock_service

# --- 测试获取当前用户通知列表 ---
@pytest.mark.anyio
async def test_get_user_notifications(client: TestClient, mock_user_service: AsyncMock):
    # Arrange
    mock_notifications = [{"id": uuid4(), "title": "Test Title", "content": "Test Content"}]
    mock_user_service.get_user_notifications.return_value = mock_notifications

    # Act
    response = client.get("/api/v1/notifications/me")

    # Assert
    assert response.status_code == 200
    assert response.json() == mock_notifications

# --- 测试标记通知已读 ---
@pytest.mark.anyio
async def test_mark_notification_as_read(client: TestClient, mock_user_service: AsyncMock):
    # Arrange
    notification_id = uuid4()
    mock_user_service.mark_notification_as_read.return_value = None

    # Act
    response = client.put(f"/api/v1/notifications/{notification_id}/read")

    # Assert
    assert response.status_code == 204

# --- 测试删除通知 ---
@pytest.mark.anyio
async def test_delete_notification(client: TestClient, mock_user_service: AsyncMock):
    # Arrange
    notification_id = uuid4()
    mock_user_service.delete_notification.return_value = None

    # Act
    response = client.delete(f"/api/v1/notifications/{notification_id}")

    # Assert
    assert response.status_code == 204

# --- 测试管理员发送系统通知 ---
@pytest.mark.anyio
async def test_send_notification(client: TestClient, mock_user_service: AsyncMock):
    # Arrange
    user_id = uuid4()
    title = "Test Title"
    content = "Test Content"
    mock_result = {"Result": "System notification sent successfully."}
    mock_user_service.send_notification.return_value = mock_result

    # Act
    response = client.post("/api/v1/notifications/send", json={
        "user_id": str(user_id),
        "title": title,
        "content": content
    })

    # Assert
    assert response.status_code == 201
    assert response.json() == mock_result