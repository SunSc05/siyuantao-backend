import pytest
import pytest_mock
from unittest.mock import AsyncMock
from uuid import uuid4, UUID
import logging
from app.services.report_service import ReportService
from app.dal.report_dal import ReportDAL
from app.exceptions import NotFoundError, DALError, ForbiddenError

# 模拟 ReportDAL 依赖
@pytest.fixture
def mock_report_dal(mocker: pytest_mock.MockerFixture):
    """Mock the ReportDAL dependency."""
    mock_dal = AsyncMock()
    mock_dal.create_report = AsyncMock()
    mock_dal.get_report_list = AsyncMock()
    mock_dal.handle_report = AsyncMock()
    return mock_dal

# 提供带有模拟 DAL 的 ReportService 实例
@pytest.fixture
def report_service(mock_report_dal: AsyncMock) -> ReportService:
    """Provides a ReportService instance with a mocked ReportDAL."""
    return ReportService(report_dal=mock_report_dal)

# 模拟数据库连接对象
@pytest.fixture
def mock_db_connection(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Mock a database connection object."""
    return AsyncMock()

# 测试 create_report 方法成功的情况
@pytest.mark.asyncio
async def test_create_report_success(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    reporter_user_id = uuid4()
    report_content = "Test report content"
    reported_user_id = uuid4()
    new_report_id = uuid4()
    result = {"NewReportID": new_report_id}

    # 配置模拟对象
    mock_report_dal.create_report.return_value = result

    # 调用服务方法
    created_report = await report_service.create_report(
        mock_db_connection,
        reporter_user_id,
        report_content,
        reported_user_id
    )

    # 断言
    assert created_report == result
    mock_report_dal.create_report.assert_called_once_with(
        mock_db_connection,
        reporter_user_id,
        report_content,
        reported_user_id,
        None,
        None
    )

# 测试 create_report 方法举报者 ID 为空的情况
@pytest.mark.asyncio
async def test_create_report_missing_reporter_id(report_service: ReportService, mock_db_connection: AsyncMock):
    # 准备数据
    reporter_user_id = None
    report_content = "Test report content"

    # 调用服务方法并断言抛出异常
    with pytest.raises(ValueError, match="举报者用户ID不能为空"):
        await report_service.create_report(
            mock_db_connection,
            reporter_user_id,
            report_content
        )

# 测试 create_report 方法举报内容为空的情况
@pytest.mark.asyncio
async def test_create_report_missing_content(report_service: ReportService, mock_db_connection: AsyncMock):
    # 准备数据
    reporter_user_id = uuid4()
    report_content = ""

    # 调用服务方法并断言抛出异常
    with pytest.raises(ValueError, match="举报内容不能为空"):
        await report_service.create_report(
            mock_db_connection,
            reporter_user_id,
            report_content
        )

# 测试 create_report 方法 DAL 层抛出异常的情况
@pytest.mark.asyncio
async def test_create_report_dal_error(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    reporter_user_id = uuid4()
    report_content = "Test report content"
    error = DALError("Database error")

    # 配置模拟对象
    mock_report_dal.create_report.side_effect = error

    # 调用服务方法并断言抛出异常
    with pytest.raises(DALError, match="Database error"):
        await report_service.create_report(
            mock_db_connection,
            reporter_user_id,
            report_content
        )

# 测试 get_reports 方法成功的情况
@pytest.mark.asyncio
async def test_get_reports_success(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    admin_id = uuid4()
    status = "Pending"
    page_number = 1
    page_size = 20
    report_list = [{"id": uuid4()}]
    total_count = 1

    # 配置模拟对象
    mock_report_dal.get_report_list.return_value = (report_list, total_count)

    # 调用服务方法
    result_report_list, result_total_count = await report_service.get_reports(
        mock_db_connection,
        admin_id,
        status,
        page_number,
        page_size
    )

    # 断言
    assert result_report_list == report_list
    assert result_total_count == total_count
    mock_report_dal.get_report_list.assert_called_once_with(
        mock_db_connection,
        status,
        page_number,
        page_size
    )

# 测试 get_reports 方法 DAL 层抛出异常的情况
@pytest.mark.asyncio
async def test_get_reports_dal_error(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    admin_id = uuid4()
    status = "Pending"
    page_number = 1
    page_size = 20
    error = DALError("Database error")

    # 配置模拟对象
    mock_report_dal.get_report_list.side_effect = error

    # 调用服务方法并断言抛出异常
    with pytest.raises(DALError, match="Database error"):
        await report_service.get_reports(
            mock_db_connection,
            admin_id,
            status,
            page_number,
            page_size
        )

# 测试 handle_report 方法成功的情况
@pytest.mark.asyncio
async def test_handle_report_success(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    admin_id = uuid4()
    report_id = uuid4()
    new_status = "Resolved"
    processing_result = "Test processing result"
    result = {"status": "success"}

    # 配置模拟对象
    mock_report_dal.handle_report.return_value = result

    # 调用服务方法
    handled_result = await report_service.handle_report(
        mock_db_connection,
        admin_id,
        report_id,
        new_status,
        processing_result
    )

    # 断言
    assert handled_result == result
    mock_report_dal.handle_report.assert_called_once_with(
        mock_db_connection,
        report_id,
        admin_id,
        new_status,
        processing_result
    )

# 测试 handle_report 方法 DAL 层抛出异常的情况
@pytest.mark.asyncio
async def test_handle_report_dal_error(report_service: ReportService, mock_report_dal: AsyncMock, mock_db_connection: AsyncMock):
    # 准备数据
    admin_id = uuid4()
    report_id = uuid4()
    new_status = "Resolved"
    processing_result = "Test processing result"
    error = DALError("Database error")

    # 配置模拟对象
    mock_report_dal.handle_report.side_effect = error

    # 调用服务方法并断言抛出异常
    with pytest.raises(DALError, match="Database error"):
        await report_service.handle_report(
            mock_db_connection,
            admin_id,
            report_id,
            new_status,
            processing_result
        )