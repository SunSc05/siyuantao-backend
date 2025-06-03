import pytest
import pytest_mock
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock
from app.dal.system_notification_dal import SystemNotificationDAL
from app.dal.base import execute_query  # 用于类型提示
from app.exceptions import NotFoundError, ForbiddenError, DALError
from datetime import datetime, timezone

# 定义测试用的固定UUID
TEST_USER_ID = UUID("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")
TEST_NOTIFICATION_ID = UUID("b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12")
TEST_INVALID_USER_ID = UUID("c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13")
TEST_INVALID_NOTIFICATION_ID = UUID("d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14")

@pytest.fixture(scope="function")
def mock_execute_query(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """模拟数据库查询执行函数"""
    return AsyncMock(spec=execute_query)

@pytest.fixture
def system_notification_dal(mock_execute_query: AsyncMock) -> SystemNotificationDAL:
    """创建带有模拟查询函数的SystemNotificationDAL实例"""
    return SystemNotificationDAL(execute_query_func=mock_execute_query)

@pytest.fixture
def mock_db_connection() -> MagicMock:
    """模拟数据库连接对象"""
    return MagicMock(spec=pyodbc.Connection)

# === 发送系统通知测试 ===
@pytest.mark.asyncio
async def test_send_system_notification_success(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试成功发送系统通知"""
    # 模拟存储过程返回成功结果
    mock_execute_query.return_value = {"Result": "系统通知发送成功。"}
    
    # 执行方法
    result = await system_notification_dal.send_system_notification(
        mock_db_connection, TEST_USER_ID, "测试标题", "测试内容"
    )
    
    # 验证调用参数
    mock_execute_query.assert_called_once_with(
        mock_db_connection,
        "{CALL sp_SendSystemNotification(?, ?, ?)}",
        (TEST_USER_ID, "测试标题", "测试内容"),
        fetchone=True
    )
    assert result == {"Result": "系统通知发送成功。"}

@pytest.mark.asyncio
async def test_send_system_notification_user_not_found(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试发送通知时目标用户不存在"""
    mock_execute_query.return_value = {"Result": "目标用户不存在，无法发送通知"}
    
    with pytest.raises(NotFoundError, match="目标用户不存在，无法发送通知"):
        await system_notification_dal.send_system_notification(
            mock_db_connection, TEST_INVALID_USER_ID, "标题", "内容"
        )

# === 获取用户通知测试 ===
@pytest.mark.asyncio
async def test_get_user_notifications_success(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试成功获取用户通知列表"""
    mock_notifications = [
        {"通知ID": TEST_NOTIFICATION_ID, "标题": "通知1", "内容": "内容1", "创建时间": datetime.now(timezone.utc), "是否已读": 0},
        {"通知ID": uuid4(), "标题": "通知2", "内容": "内容2", "创建时间": datetime.now(timezone.utc), "是否已读": 1}
    ]
    mock_execute_query.return_value = mock_notifications
    
    result = await system_notification_dal.get_user_notifications(
        mock_db_connection, TEST_USER_ID, is_read=0, page_number=1, page_size=10
    )
    
    mock_execute_query.assert_called_once_with(
        mock_db_connection,
        "{CALL sp_GetUserNotifications(?, ?, ?, ?)}",
        (TEST_USER_ID, 0, 1, 10),
        fetchall=True
    )
    assert result == mock_notifications

@pytest.mark.asyncio
async def test_get_user_notifications_user_not_found(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试获取通知时用户不存在"""
    mock_execute_query.return_value = [{"用户不存在"}]  # 模拟存储过程返回的错误标识
    
    with pytest.raises(NotFoundError, match="用户不存在"):
        await system_notification_dal.get_user_notifications(
            mock_db_connection, TEST_INVALID_USER_ID, page_number=1, page_size=10
        )

# === 标记通知已读测试 ===
@pytest.mark.asyncio
async def test_mark_notification_as_read_success(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试成功标记通知为已读"""
    mock_execute_query.return_value = {"Result": "通知标记为已读成功。"}
    
    result = await system_notification_dal.mark_notification_as_read(
        mock_db_connection, TEST_NOTIFICATION_ID, TEST_USER_ID
    )
    
    mock_execute_query.assert_called_once_with(
        mock_db_connection,
        "{CALL sp_MarkNotificationAsRead(?, ?)}",
        (TEST_NOTIFICATION_ID, TEST_USER_ID),
        fetchone=True
    )
    assert result is True

@pytest.mark.asyncio
async def test_mark_notification_as_read_not_found(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试标记已读时通知不存在"""
    mock_execute_query.return_value = {"Result": "通知不存在"}
    
    with pytest.raises(NotFoundError, match="通知不存在"):
        await system_notification_dal.mark_notification_as_read(
            mock_db_connection, TEST_INVALID_NOTIFICATION_ID, TEST_USER_ID
        )

@pytest.mark.asyncio
async def test_mark_notification_as_read_no_permission(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试标记已读时无权限"""
    mock_execute_query.return_value = {"Result": "无权标记此通知为已读。"}
    
    with pytest.raises(ForbiddenError, match="无权限标记此通知"):
        await system_notification_dal.mark_notification_as_read(
            mock_db_connection, TEST_NOTIFICATION_ID, TEST_INVALID_USER_ID
        )

# === 逻辑删除通知测试 ===
@pytest.mark.asyncio
async def test_delete_notification_success(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试成功逻辑删除通知"""
    mock_execute_query.return_value = {"Result": "通知已标记为删除。"}
    
    result = await system_notification_dal.delete_notification(
        mock_db_connection, TEST_NOTIFICATION_ID, TEST_USER_ID
    )
    
    mock_execute_query.assert_called_once_with(
        mock_db_connection,
        "{CALL sp_DeleteNotification(?, ?)}",
        (TEST_NOTIFICATION_ID, TEST_USER_ID),
        fetchone=True
    )
    assert result is True

@pytest.mark.asyncio
async def test_delete_notification_not_found(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试删除时通知不存在"""
    mock_execute_query.return_value = {"Result": "通知不存在"}
    
    with pytest.raises(NotFoundError, match="通知不存在"):
        await system_notification_dal.delete_notification(
            mock_db_connection, TEST_INVALID_NOTIFICATION_ID, TEST_USER_ID
        )

@pytest.mark.asyncio
async def test_delete_notification_no_permission(
    system_notification_dal: SystemNotificationDAL,
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock
):
    """测试删除时无权限"""
    mock_execute_query.return_value = {"Result": "无权删除此通知。"}
    
    with pytest.raises(ForbiddenError, match="无权限删除此通知"):
        await system_notification_dal.delete_notification(
            mock_db_connection, TEST_NOTIFICATION_ID, TEST_INVALID_USER_ID
        )