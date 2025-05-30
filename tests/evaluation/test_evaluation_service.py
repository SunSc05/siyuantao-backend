import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.services.evaluation_service import EvaluationService
from app.dal.evaluation_dal import EvaluationDAL
from app.schemas.evaluation_schemas import EvaluationCreateSchema, EvaluationResponseSchema
from app.exceptions import DALError, NotFoundError, ForbiddenError

@pytest.fixture
def mock_evaluation_dal(mocker) -> AsyncMock:
    """Mock the EvaluationDAL dependency."""
    return mocker.create_autospec(EvaluationDAL, instance=True, spec_set=True)

@pytest.fixture
def evaluation_service(mock_evaluation_dal: AsyncMock) -> EvaluationService:
    """Provide an instance of EvaluationService with a mocked DAL."""
    return EvaluationService(mock_evaluation_dal)

@pytest.fixture
def mock_conn() -> MagicMock:
    """Mock a pyodbc connection object."""
    return MagicMock()

@pytest.mark.asyncio
async def test_create_evaluation_success(evaluation_service: EvaluationService, mock_evaluation_dal: AsyncMock, mock_conn: MagicMock):
    """测试成功创建评价。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    seller_id = uuid4() # Add seller_id
    evaluation_data = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=5, comment="非常满意！")

    # Mock DAL的create_evaluation方法不返回任何东西，因为它只是执行插入
    mock_evaluation_dal.create_evaluation.return_value = None

    # Mock DAL的get_evaluation_by_id方法返回一个完整的EvaluationResponseSchema
    expected_evaluation_response = EvaluationResponseSchema(
        evaluation_id=uuid4(), # 假设一个UUID
        order_id=order_id,
        product_id=product_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        rating=evaluation_data.rating,
        comment=evaluation_data.comment,
        created_at=datetime.now(timezone.utc)
    )
    # 由于Service层在创建后会尝试获取完整的评价对象，我们需要mock这个行为
    # 注意：当前Service层的create_evaluation方法中，返回的是一个基于输入数据的占位符Schema
    # 如果DAL层能够返回完整的创建对象，这里需要调整mock_evaluation_dal的行为
    # 暂时按照Service层当前实现，它会构造一个EvaluationResponseSchema

    # 调用Service方法
    created_evaluation = await evaluation_service.create_evaluation(mock_conn, evaluation_data, buyer_id)

    # 断言DAL方法被正确调用
    mock_evaluation_dal.create_evaluation.assert_called_once_with(
        conn=mock_conn,
        order_id=evaluation_data.order_id,
        product_id=evaluation_data.product_id, # Add product_id
        buyer_id=buyer_id,
        rating=evaluation_data.rating,
        comment=evaluation_data.comment
    )

    # 断言返回结果的正确性 (基于Service层当前构造返回值的逻辑)
    assert created_evaluation.order_id == evaluation_data.order_id
    assert created_evaluation.buyer_id == buyer_id
    assert created_evaluation.rating == evaluation_data.rating
    assert created_evaluation.comment == evaluation_data.comment
    assert created_evaluation.product_id == evaluation_data.product_id # Add product_id assertion
    # 对于created_at和evaluation_id，由于Service层是占位符，这里只检查类型或存在性
    assert isinstance(created_evaluation.evaluation_id, UUID)
    assert isinstance(created_evaluation.created_at, datetime)

@pytest.mark.asyncio
async def test_create_evaluation_value_error_rating_out_of_range(evaluation_service: EvaluationService, mock_conn: MagicMock):
    """测试评分超出范围时抛出ValueError。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    evaluation_data_low = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=0, comment="")
    evaluation_data_high = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=6, comment="")

    with pytest.raises(ValueError, match="Rating must be between 1 and 5."):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data_low, buyer_id)

    with pytest.raises(ValueError, match="Rating must be between 1 and 5."):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data_high, buyer_id)

@pytest.mark.asyncio
async def test_create_evaluation_dal_error(evaluation_service: EvaluationService, mock_evaluation_dal: AsyncMock, mock_conn: MagicMock):
    """测试DAL层抛出DALError时，Service层是否正确传递。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    evaluation_data = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=4, comment="")

    mock_evaluation_dal.create_evaluation.side_effect = DALError("数据库连接失败")

    with pytest.raises(DALError, match="数据库连接失败"):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data, buyer_id)

    mock_evaluation_dal.create_evaluation.assert_called_once()

@pytest.mark.asyncio
async def test_create_evaluation_not_found_error(evaluation_service: EvaluationService, mock_evaluation_dal: AsyncMock, mock_conn: MagicMock):
    """测试DAL层抛出NotFoundError时，Service层是否正确传递。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    evaluation_data = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=4, comment="")

    mock_evaluation_dal.create_evaluation.side_effect = NotFoundError("订单未找到")

    with pytest.raises(NotFoundError, match="订单未找到"):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data, buyer_id)

    mock_evaluation_dal.create_evaluation.assert_called_once()

@pytest.mark.asyncio
async def test_create_evaluation_forbidden_error(evaluation_service: EvaluationService, mock_evaluation_dal: AsyncMock, mock_conn: MagicMock):
    """测试DAL层抛出ForbiddenError时，Service层是否正确传递。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    evaluation_data = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=4, comment="")

    mock_evaluation_dal.create_evaluation.side_effect = ForbiddenError("无权评价")

    with pytest.raises(ForbiddenError, match="无权评价"):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data, buyer_id)

    mock_evaluation_dal.create_evaluation.assert_called_once()

@pytest.mark.asyncio
async def test_create_evaluation_unexpected_exception(evaluation_service: EvaluationService, mock_evaluation_dal: AsyncMock, mock_conn: MagicMock):
    """测试DAL层抛出其他通用异常时，Service层是否转换为DALError。"""
    buyer_id = uuid4()
    order_id = uuid4()
    product_id = uuid4() # Add product_id
    evaluation_data = EvaluationCreateSchema(order_id=order_id, product_id=product_id, user_id=buyer_id, rating=4, comment="")

    mock_evaluation_dal.create_evaluation.side_effect = Exception("未知错误")

    with pytest.raises(DALError, match="An unexpected error occurred during evaluation creation: 未知错误"):
        await evaluation_service.create_evaluation(mock_conn, evaluation_data, buyer_id)

    mock_evaluation_dal.create_evaluation.assert_called_once()
