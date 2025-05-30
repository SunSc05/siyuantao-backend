import pytest
from fastapi import status
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.main import app
from app.dependencies import get_evaluation_service, get_current_user, get_db_connection
from app.services.evaluation_service import EvaluationService
from app.schemas.evaluation_schemas import EvaluationCreateSchema, EvaluationResponseSchema
from app.exceptions import IntegrityError, ForbiddenError, NotFoundError, DALError

# Mock dependencies
@pytest.fixture
def mock_evaluation_service():
    return AsyncMock(spec=EvaluationService)

@pytest.fixture
def mock_current_user():
    return {"user_id": str(uuid4()), "username": "testuser"}

@pytest.fixture
def mock_db_connection():
    return MagicMock() # pyodbc.Connection is a synchronous object, MagicMock is sufficient

# Override dependencies for testing
app.dependency_overrides[get_evaluation_service] = lambda: MagicMock(spec=EvaluationService)
app.dependency_overrides[get_current_user] = lambda: {"user_id": str(uuid4()), "username": "testuser"}
app.dependency_overrides[get_db_connection] = lambda: MagicMock()

@pytest.mark.asyncio
async def test_create_new_evaluation_success(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test successful creation of a new evaluation."""
    # Override specific dependencies for this test to use the mocks passed as fixtures
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 5,
        "comment": "Excellent product!"
    }
    # Generate UUIDs for expected_response to match EvaluationResponseSchema
    test_evaluation_id = uuid4()
    test_buyer_id = uuid4()

    expected_response = EvaluationResponseSchema(
        evaluation_id=test_evaluation_id,
        order_id=evaluation_data["order_id"],
        buyer_id=test_buyer_id, # This will be mocked in service
        rating=evaluation_data["rating"],
        comment=evaluation_data["comment"],
        evaluation_date="2023-01-01T12:00:00"
    )
    mock_evaluation_service.create_evaluation.return_value = expected_response

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == expected_response.model_dump(by_alias=True, mode='json') # Changed to model_dump and mode='json'
    mock_evaluation_service.create_evaluation.assert_called_once_with(
        mock_db_connection,
        EvaluationCreateSchema(**evaluation_data),
        mock_current_user["user_id"]
    )

@pytest.mark.asyncio
async def test_create_new_evaluation_unauthorized(client, mock_evaluation_service, mock_db_connection):
    """Test creating evaluation without a valid user (unauthorized)."""
    # Temporarily remove get_current_user override to simulate unauthorized access
    with client.app.dependency_overrides: # Use client.app.dependency_overrides context manager
        client.app.dependency_overrides[get_current_user] = lambda: None # Simulate no current user

        evaluation_data = {
            "order_id": 1,
            "rating": 5,
            "comment": "Excellent product!"
        }

        response = await client.post("/evaluations/", json=evaluation_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "无法获取当前用户信息"}
        mock_evaluation_service.create_evaluation.assert_not_called()

    # Restore original override for other tests
    # app.dependency_overrides[get_current_user] = lambda: {"user_id": str(uuid4()), "username": "testuser"} # Removed redundant restoration

@pytest.mark.asyncio
async def test_create_new_evaluation_integrity_error(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of IntegrityError during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 5,
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = IntegrityError("Evaluation already exists for this order.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Evaluation already exists for this order."}

@pytest.mark.asyncio
async def test_create_new_evaluation_value_error(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of ValueError during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 0, # Invalid rating
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = ValueError("Rating must be between 1 and 5.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Rating must be between 1 and 5."}

@pytest.mark.asyncio
async def test_create_new_evaluation_forbidden_error(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of ForbiddenError during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 5,
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = ForbiddenError("User not allowed to evaluate this order.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "User not allowed to evaluate this order."}

@pytest.mark.asyncio
async def test_create_new_evaluation_not_found_error(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of NotFoundError during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 999, # Non-existent order
        "rating": 5,
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = NotFoundError("Order not found.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Order not found."}

@pytest.mark.asyncio
async def test_create_new_evaluation_dal_error(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of DALError during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 5,
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = DALError("Database operation failed due to connection issue.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "数据库操作失败: Database operation failed due to connection issue."}

@pytest.mark.asyncio
async def test_create_new_evaluation_generic_exception(client, mock_evaluation_service, mock_current_user, mock_db_connection):
    """Test handling of a generic Exception during evaluation creation."""
    # Use the client fixture's dependency overrides, no need to re-override here
    # app.dependency_overrides[get_evaluation_service] = lambda: mock_evaluation_service # Removed redundant override
    # app.dependency_overrides[get_current_user] = lambda: mock_current_user # Removed redundant override
    # app.dependency_overrides[get_db_connection] = lambda: mock_db_connection # Removed redundant override

    evaluation_data = {
        "order_id": 1,
        "rating": 5,
        "comment": "Excellent product!"
    }
    mock_evaluation_service.create_evaluation.side_effect = Exception("Unexpected server error.")

    response = await client.post("/evaluations/", json=evaluation_data)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "服务器内部错误: Unexpected server error."}

# Restore original dependencies after all tests are run
@pytest.fixture(autouse=True)
def restore_dependencies():
    yield
    # app.dependency_overrides.clear() # Removed redundant clear, conftest handles restoration

# Removed redundant overrides outside tests
# app.dependency_overrides[get_evaluation_service] = lambda: MagicMock(spec=EvaluationService)
# app.dependency_overrides[get_current_user] = lambda: {"user_id": str(uuid4()), "username": "testuser"}
# app.dependency_overrides[get_db_connection] = lambda: MagicMock()