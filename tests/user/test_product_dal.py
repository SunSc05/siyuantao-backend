import pytest
from unittest.mock import AsyncMock, MagicMock
from app.dal.product_dal import ProductDAL
from databases import Database

@pytest.fixture
def mock_db_connection(mocker: pytest_mock.MockerFixture):
    return MagicMock(spec=Database)

@pytest.mark.asyncio
async def test_sp_batch_review_products(mock_db_connection: MagicMock):
    # 初始化DAL
    dal = ProductDAL(mock_db_connection)
    
    # 模拟参数
    product_ids = ["123e4567-e89b-12d3-a456-426614174000", "456e4567-e89b-12d3-a456-426614174000"]
    admin_id = "789e4567-e89b-12d3-a456-426614174000"
    new_status = "Active"
    reason = ""
    
    # 调用方法
    await dal.batch_review_products(
        product_ids=product_ids,
        admin_id=admin_id,
        new_status=new_status,
        reason=reason
    )
    
    # 断言SQL执行（示例，需根据实际存储过程参数调整）
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_BatchReviewProducts @productIds = '123e4567-e89b-12d3-a456-426614174000,456e4567-e89b-12d3-a456-426614174000', @adminId = '789e4567-e89b-12d3-a456-426614174000', @newStatus = 'Active', @reason = ''"
    )