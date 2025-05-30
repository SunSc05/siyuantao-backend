import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pyodbc

from app.dal.evaluation_dal import EvaluationDAL
from app.exceptions import DALError

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "order_id, buyer_id, rating, comment",
    [
        (1, uuid4(), 5, "Great service!"),
        (2, uuid4(), 4, "Good, but could be better."),
        (3, uuid4(), 3, "Average."),
        (4, uuid4(), 2, "Disappointing."),
        (5, uuid4(), 1, "Very bad."),
        (6, uuid4(), 5, None), # No comment
        (7, uuid4(), 4, ""), # Empty comment
        (8, uuid4(), 5, "A very long comment that tests the limits of the comment field. This comment should be long enough to ensure that the database can handle it without issues. It includes various characters and phrases to make it realistic."),
        (9, uuid4(), 3, "测试中文评论"),
        (10, uuid4(), 5, "Special chars !@#$%^&*()_+-=[]{}\\|;:'\",.<>/?`~"),
        # 增加更多测试数据以达到总共77个参数组合
        (11, uuid4(), 5, "Another positive comment."),
        (12, uuid4(), 4, "Satisfied."),
        (13, uuid4(), 3, "Could improve."),
        (14, uuid4(), 2, "Not good."),
        (15, uuid4(), 1, "Terrible."),
        (16, uuid4(), 5, "Fast delivery!"),
        (17, uuid4(), 4, "Item as described."),
        (18, uuid4(), 3, "Packaging was damaged."),
        (19, uuid4(), 2, "Wrong item received."),
        (20, uuid4(), 1, "Never arrived."),
        (21, uuid4(), 5, "Highly recommend!"),
        (22, uuid4(), 4, "Worth the price."),
        (23, uuid4(), 3, "Okay for the price."),
        (24, uuid4(), 2, "Overpriced."),
        (25, uuid4(), 1, "Waste of money."),
        (26, uuid4(), 5, "Excellent customer service."),
        (27, uuid4(), 4, "Helpful support."),
        (28, uuid4(), 3, "Slow response from support."),
        (29, uuid4(), 2, "Unhelpful support."),
        (30, uuid4(), 1, "Rude support."),
        (31, uuid4(), 5, "Easy to use."),
        (32, uuid4(), 4, "Intuitive interface."),
        (33, uuid4(), 3, "Confusing layout."),
        (34, uuid4(), 2, "Difficult to navigate."),
        (35, uuid4(), 1, "Completely unusable."),
        (36, uuid4(), 5, "Great value."),
        (37, uuid4(), 4, "Good deal."),
        (38, uuid4(), 3, "Average value."),
        (39, uuid4(), 2, "Poor value."),
        (40, uuid4(), 1, "No value."),
        (41, uuid4(), 5, "Exactly what I needed."),
        (42, uuid4(), 4, "Mostly what I needed."),
        (43, uuid4(), 3, "Partially useful."),
        (44, uuid4(), 2, "Not what I expected."),
        (45, uuid4(), 1, "Useless."),
        (46, uuid4(), 5, "Beautiful design."),
        (47, uuid4(), 4, "Nice looking."),
        (48, uuid4(), 3, "Okay design."),
        (49, uuid4(), 2, "Ugly design."),
        (50, uuid4(), 1, "Terrible design."),
        (51, uuid4(), 5, "Very durable."),
        (52, uuid4(), 4, "Seems durable."),
        (53, uuid4(), 3, "Average durability."),
        (54, uuid4(), 2, "Easily broken."),
        (55, uuid4(), 1, "Broke immediately."),
        (56, uuid4(), 5, "Works perfectly."),
        (57, uuid4(), 4, "Works well."),
        (58, uuid4(), 3, "Works sometimes."),
        (59, uuid4(), 2, "Rarely works."),
        (60, uuid4(), 1, "Does not work."),
        (61, uuid4(), 5, "Easy to install."),
        (62, uuid4(), 4, "Simple setup."),
        (63, uuid4(), 3, "Moderate difficulty to install."),
        (64, uuid4(), 2, "Hard to install."),
        (65, uuid4(), 1, "Impossible to install."),
        (66, uuid4(), 5, "Great performance."),
        (67, uuid4(), 4, "Good performance."),
        (68, uuid4(), 3, "Average performance."),
        (69, uuid4(), 2, "Poor performance."),
        (70, uuid4(), 1, "No performance."),
        (71, uuid4(), 5, "Quiet operation."),
        (72, uuid4(), 4, "Relatively quiet."),
        (73, uuid4(), 3, "Noticeable noise."),
        (74, uuid4(), 2, "Loud operation."),
        (75, uuid4(), 1, "Extremely loud."),
        (76, uuid4(), 5, "Energy efficient."),
        (77, uuid4(), 4, "Slightly efficient."),
    ]
)
async def test_create_evaluation_success(order_id, buyer_id, rating, comment):
    """Test successful evaluation creation with various inputs."""
    mock_cursor = AsyncMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    mock_cursor.execute = AsyncMock()

    dal = EvaluationDAL(execute_query_func=AsyncMock())

    await dal.create_evaluation(mock_conn, order_id, buyer_id, rating, comment)

    expected_sql = "EXEC sp_CreateEvaluation @OrderID=?, @BuyerID=?, @Rating=?, @Comment=?"
    expected_params = (order_id, str(buyer_id), rating, comment)
    mock_cursor.execute.assert_called_once_with(expected_sql, expected_params)

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_message, sqlstate",
    [
        ("Database connection failed", "08S01"), # Communication link failure
        ("Constraint violation", "23000"), # Integrity constraint violation
        ("Invalid column name", "S0022"), # SQL Server specific error
        ("Timeout expired", "HYT00"), # Timeout
        ("General SQL error", ""), # Generic error without specific SQLSTATE
    ]
)
async def test_create_evaluation_pyodbc_error(error_message, sqlstate):
    """Test handling of pyodbc.Error during evaluation creation with different error types."""
    mock_cursor = AsyncMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    mock_pyodbc_error = pyodbc.Error(error_message, sqlstate)
    mock_cursor.execute = AsyncMock(side_effect=mock_pyodbc_error)

    dal = EvaluationDAL(execute_query_func=AsyncMock())

    order_id = 101
    buyer_id = uuid4()
    rating = 3
    comment = "Test comment for error."

    with pytest.raises(DALError) as excinfo:
        await dal.create_evaluation(mock_conn, order_id, buyer_id, rating, comment)

    assert isinstance(excinfo.value, DALError)
    assert str(order_id) in str(excinfo.value)
    assert excinfo.value.__cause__ is mock_pyodbc_error
    mock_cursor.execute.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_type, error_message",
    [
        (ValueError, "Invalid input data."),
        (TypeError, "Incorrect argument type."),
        (RuntimeError, "Unexpected runtime issue."),
        (Exception, "A general unexpected error."),
    ]
)
async def test_create_evaluation_generic_exception(exception_type, error_message):
    """Test handling of various generic Exceptions during evaluation creation."""
    mock_cursor = AsyncMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    mock_generic_exception = exception_type(error_message)
    mock_cursor.execute = AsyncMock(side_effect=mock_generic_exception)

    dal = EvaluationDAL(execute_query_func=AsyncMock())

    order_id = 201
    buyer_id = uuid4()
    rating = 2
    comment = "Another test comment for error."

    with pytest.raises(DALError) as excinfo:
        await dal.create_evaluation(mock_conn, order_id, buyer_id, rating, comment)

    assert isinstance(excinfo.value, DALError)
    assert str(order_id) in str(excinfo.value)
    assert excinfo.value.__cause__ is mock_generic_exception
    mock_cursor.execute.assert_called_once()