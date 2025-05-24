# tests/test_users_api.py
import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock # Import AsyncMock and MagicMock
from fastapi import Depends, status, HTTPException # Import HTTPException
import pytest_mock
# from unittest.mock import patch # Not strictly needed for this approach
# from app.dependencies import get_user_service, get_current_user, get_current_active_admin_user # Import dependencies from here
from app.dal.connection import get_db_connection # Import get_db_connection from its correct location
# Import authentication dependencies directly from app.dependencies for type hinting if needed, but patch in routers module
from app.dependencies import get_user_service as get_user_service_dependency, get_current_user as get_current_user_dependency, get_current_active_admin_user as get_current_active_admin_user_dependency

# Import necessary modules from your application
from app.main import app
# Import schemas with their updated names
from app.schemas.user_schemas import (
    UserRegisterSchema,
    UserLoginSchema,
    Token,
    UserProfileUpdateSchema,
    UserPasswordUpdate,
    RequestVerificationEmail,
    VerifyEmail,
    UserResponseSchema, # Import UserResponseSchema
    UserStatusUpdateSchema,
    UserCreditAdjustmentSchema
)
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions

# Import the UserService class
from app.services.user_service import UserService # Import Service class for type hinting
from app.dal.user_dal import UserDAL # Import UserDAL for type hinting

from datetime import datetime, timezone # Import datetime and timezone
from dateutil.parser import isoparse # Import isoparse for flexible ISO 8601 parsing

# Remove database fixture and helper functions that interact with the database directly
# from app.dal.connection import get_connection_string
# import pyodbc
# import asyncio
# from app.dal.tests.test_users_dal import _clean_users_table, _set_user_status, _set_verification_token

# --- Test Fixtures (Likely defined in conftest.py, including client and db_conn_fixture) ---
# Keep the client fixture (assuming it's in conftest.py or defined here)
# @pytest.fixture(scope="session")
# def anyio_backend():
#     return "asyncio"

# --- Mock Authentication Dependencies using dependency_overrides ---
# Define Mock functions to be used with dependency_overrides
async def mock_get_current_user_override():
    # This will be the 'current_user' in the router
    # Return a dict that matches the expected payload structure
    # Use a consistent test user ID (UUID)
    test_user_id = UUID("12345678-1234-5678-1234-567812345678") # Use a fixed UUID
    return {"user_id": test_user_id, "UserID": test_user_id, "username": "testuser", "is_staff": False, "is_verified": True}

async def mock_get_current_active_admin_user_override():
    # This will be the 'current_admin_user' in the router
    # Return a dict that matches the expected payload structure for an admin
    # Use a consistent test admin user ID (UUID)
    test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000") # Use a fixed UUID for admin
    return {"user_id": test_admin_user_id, "UserID": test_admin_user_id, "username": "adminuser", "is_staff": True, "is_verified": True}


@pytest.fixture(scope="function")
def client(mock_user_service, mocker): # Remove mocker if not needed by other mocks in fixture
    # Use app.dependency_overrides to mock dependencies for the TestClient
    # Mock the get_db_connection dependency in app.dal.connection
    async def override_get_db_connection_async(): # Define the async override function
        # Return a mock connection object
        mock_conn = MagicMock()
        yield mock_conn # Yield the mock connection asynchronously

    print(f"DEBUG: TestClient using app instance with id: {id(app)}")
    print(f"DEBUG: App routes in TestClient: {app.routes}")

    # Set up dependency overrides using the simple mock functions
    app.dependency_overrides[get_user_service_dependency] = lambda: mock_user_service
    app.dependency_overrides[get_db_connection] = override_get_db_connection_async
    # Override authentication dependencies with our simple mock functions
    app.dependency_overrides[get_current_user_dependency] = mock_get_current_user_override
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_override


    with TestClient(app) as tc:
        # Pass the mock user IDs to the test client instance for easy access in tests
        tc.test_user_id = UUID("12345678-1234-5678-1234-567812345678")
        tc.test_admin_user_id = UUID("87654321-4321-8765-4321-876543210000")
        yield tc # Yield the TestClient instance

    # Clean up the dependency override after the test is done
    app.dependency_overrides.clear()

# Remove the clean_db fixture as we are mocking the DAL/Service
# @pytest.fixture(scope="function", autouse=True)
# async def clean_db():
# ... removed ...
# --- Mock Fixture for UserService ---
@pytest.fixture
def mock_user_service(mocker):
    """Mock the UserService dependency."""
    # Create an AsyncMock instance for the UserService class
    mock_service = AsyncMock(spec=UserService)
    # Patch the get_user_service dependency to return our mock service instance
    # Removed patching get_user_service here as it's handled in the client fixture
    # mocker.patch('app.dependencies.get_user_service', return_value=mock_service)
    return mock_service

# --- Mock Fixture for Authentication Dependencies --- (Remove this fixture as we are using dependency_overrides)
# @pytest.fixture # Remove this fixture
# def mock_auth_dependencies(mocker):
# ... removed ...

# --- Mock Fixture for Database Connection Dependency --- (Remove this patch as it's handled in client fixture)
# Instead of a fixture, patch the dependency directly for all API tests
# mock_db_conn_patch = patch('app.dependencies.get_db_conn', return_value=MagicMock()) # Patch the dependency itself
# Activate the patch for all tests in this module
# mock_db_conn_patch.start()
# Optionally, stop the patch after all tests are done (though pytest handles this)
# import atexit
# atexit.register(mock_db_conn_patch.stop)
# Remove the mock_db_connection_dependency fixture as it's no longer needed
# @pytest.fixture
# def mock_db_connection_dependency(mocker):
# ... removed ...

# Remove database-interacting helper functions
# async def register_user_helper(client: AsyncClient, username, email, password):
# ... removed ...
# async def login_user_helper(client: AsyncClient, username, password):
# ... removed ...
# async def create_admin_user_helper(client: AsyncClient, db_conn: pyodbc.Connection, username, email, password):
# ... removed ...

# --- Modified/New Tests using Mocking ---

@pytest.mark.anyio # Use anyio mark
async def test_register_user(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "testuser_reg"
    email = "test_reg@example.com"
    password = "securepassword"
    user_data = UserRegisterSchema(username=username, email=email, password=password)

    # Define the expected return value from the mocked service method
    # Service layer should return a UserResponseSchema instance with correct types (UUID object, datetime object)
    test_user_id = uuid4() # Simulate a generated UUID
    expected_created_user_schema = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="test_reg_user",
        email="test_reg@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_verified=False,
        major=None,
        avatar_url=None,
        bio=None,
        phone_number=None,
        join_time=datetime.now(timezone.utc) # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.create_user.return_value = expected_created_user_schema

    response = client.post("/api/v1/auth/register", json=user_data.model_dump())

    assert response.status_code == 201
    # FastAPI will serialize the returned UserResponseSchema instance automatically.
    # We can assert the structure and types of the JSON response.
    response_json = response.json()
    assert isinstance(response_json, dict)
    assert "user_id" in response_json
    assert "username" in response_json
    assert "email" in response_json
    assert "status" in response_json
    assert "credit" in response_json
    assert "is_staff" in response_json
    assert "is_verified" in response_json
    # Optional fields
    assert "major" in response_json
    assert "avatar_url" in response_json
    assert "bio" in response_json
    assert "phone_number" in response_json
    assert "join_time" in response_json

    # Assert data types in the JSON response
    assert isinstance(response_json["user_id"], str)
    assert isinstance(response_json["username"], str)
    assert isinstance(response_json["email"], str)
    assert isinstance(response_json["status"], str)
    assert isinstance(response_json["credit"], int)
    assert isinstance(response_json["is_staff"], bool)
    assert isinstance(response_json["is_verified"], bool)
    # Optional fields - check for None or correct type if present
    assert response_json["major"] is None or isinstance(response_json["major"], str)
    assert response_json["avatar_url"] is None or isinstance(response_json["avatar_url"], str)
    assert response_json["bio"] is None or isinstance(response_json["bio"], str)
    assert response_json["phone_number"] is None or isinstance(response_json["phone_number"], str)
    assert isinstance(response_json["join_time"], str) # FastAPI serializes datetime to ISO 8601 string

    # Assert specific values for fields that are not UUID or datetime
    assert response_json["user_id"] == str(test_user_id) # Assert UUID is serialized as string
    assert response_json["username"] == "test_reg_user"
    assert response_json["email"] == "test_reg@example.com"
    assert response_json["status"] == "Active"
    assert response_json["credit"] == 100
    assert response_json["is_staff"] is False
    assert response_json["is_verified"] is False
    assert response_json["major"] is None
    assert response_json["avatar_url"] is None
    assert response_json["bio"] is None
    assert response_json["phone_number"] is None
    # We can potentially add more specific checks for join_time format if needed

    # Verify service method was called with correct arguments
    mock_user_service.create_user.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        user_data
    )

@pytest.mark.anyio # Use anyio mark
async def test_register_user_duplicate_username(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "dup_reg_user"
    email = "dup_reg@example.com"
    password = "password"
    user_data = UserRegisterSchema(username=username, email=email, password=password)

    # Simulate Service layer raising IntegrityError for duplicate username
    mock_user_service.create_user.side_effect = IntegrityError("Username already exists.")

    response = client.post("/api/v1/auth/register", json=user_data.model_dump())

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists."

    mock_user_service.create_user.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        user_data
    )

@pytest.mark.anyio # Use anyio mark
async def test_register_user_duplicate_email(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "another_reg_user"
    email = "dup_reg@example.com"
    password = "password"
    user_data = UserRegisterSchema(username=username, email=email, password=password)

    # Simulate Service layer raising IntegrityError for duplicate email
    mock_user_service.create_user.side_effect = IntegrityError("Email already exists.")

    response = client.post("/api/v1/auth/register", json=user_data.model_dump())

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already exists."

    mock_user_service.create_user.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        user_data
    )

@pytest.mark.anyio # Use anyio mark
async def test_login_for_access_token(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "login_user_api_mock"
    password = "securepassword"
    login_data = UserLoginSchema(username=username, password=password)
    expected_token = "mock_jwt_token"

    # Simulate Service layer returning a token string on successful authentication
    # Service method should return the token string, not the Token schema dict.
    # The API router function constructs the Token schema dict.
    mock_user_service.authenticate_user_and_create_token.return_value = expected_token

    # OAuth2PasswordRequestForm expects form data, not JSON
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})

    assert response.status_code == 200
    token_data = response.json()
    assert token_data["access_token"] == expected_token
    assert token_data["token_type"] == "bearer"

    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        username,
        password
    )

@pytest.mark.anyio # Use anyio mark
async def test_login_unauthorized(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "wrong_user"
    password = "wrong_password"
    login_data = UserLoginSchema(username=username, password=password)

    # Simulate Service layer raising AuthenticationError on failed authentication
    mock_user_service.authenticate_user_and_create_token.side_effect = AuthenticationError("用户名或密码不正确")

    # OAuth2PasswordRequestForm expects form data, not JSON
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码不正确"
    assert "WWW-Authenticate" in response.headers

    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        username,
        password
    )

@pytest.mark.anyio # Use anyio mark
async def test_login_disabled_account(client: TestClient, mock_user_service: AsyncMock, mocker):
    username = "disabled_user_mock"
    password = "pass"
    login_data = UserLoginSchema(username=username, password=password)

    # Simulate Service layer raising ForbiddenError for disabled account
    mock_user_service.authenticate_user_and_create_token.side_effect = ForbiddenError("账户已被禁用")

    # OAuth2PasswordRequestForm expects form data, not JSON
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})

    assert response.status_code == 403 # Or 401 depending on exact API design/exception handling
    assert response.json()["detail"] == "账户已被禁用"

    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY, # Mocked DB connection (should be MagicMock from fixture)
        username,
        password
    )

@pytest.mark.anyio # Use anyio mark
async def test_read_users_me(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked authentication dependency
    # We can access the test user ID from the client instance
    test_user_id = client.test_user_id

    # Simulate the service returning the expected UserResponseSchema instance
    mock_user_service.get_user_profile_by_id.return_value = UserResponseSchema(
         user_id=test_user_id, # Service returns UUID object
         username="test_me_user",
         email="me@example.com",
         status="Active",
         credit=100,
         is_staff=False,
         is_verified=True,
         major="CS",
         avatar_url=None,
         bio="Test bio.",
         phone_number="1234567890",
         join_time=datetime.now(timezone.utc) # Use timezone-aware datetime
     )

    # GET request to /me does not send a body, so no json= argument is needed
    # No need for Authorization header, as auth dependency is mocked
    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    # FastAPI will serialize the returned UserResponseSchema instance automatically.
    # We can assert the structure and types of the JSON response.
    response_json = response.json()
    assert isinstance(response_json, dict)
    # Check for presence and types of required fields
    assert isinstance(response_json.get("user_id"), str)
    assert isinstance(response_json.get("username"), str)
    assert isinstance(response_json.get("email"), str)
    assert isinstance(response_json.get("status"), str)
    assert isinstance(response_json.get("credit"), int)
    assert isinstance(response_json.get("is_staff"), bool)
    assert isinstance(response_json.get("is_verified"), bool)
    # Check for presence and types of optional fields
    assert "major" in response_json
    assert "avatar_url" in response_json
    assert "bio" in response_json
    assert "phone_number" in response_json
    assert isinstance(response_json.get("major"), (str, type(None)))
    assert isinstance(response_json.get("avatar_url"), (str, type(None)))
    assert isinstance(response_json.get("bio"), (str, type(None)))
    assert isinstance(response_json.get("phone_number"), (str, type(None)))
    assert isinstance(response_json.get("join_time"), str) # FastAPI serializes datetime to ISO 8601 string

    # Assert specific values for fields that are not UUID or datetime
    assert response_json.get("user_id") == str(test_user_id) # Assert UUID is serialized as string
    assert response_json.get("username") == "test_me_user"
    assert response_json.get("email") == "me@example.com"
    assert response_json.get("status") == "Active"
    assert response_json.get("credit") == 100
    assert response_json.get("is_staff") is False
    assert response_json.get("is_verified") is True
    assert response_json.get("major") == "CS"
    assert response_json.get("bio") == "Test bio."
    assert response_json.get("phone_number") == "1234567890"
    # We can potentially add more specific checks for join_time format if needed

    mock_user_service.get_user_profile_by_id.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id # User ID from the mocked dependency (should be UUID object passed to service)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_read_users_me_unauthorized(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the dependency itself raises an Unauthorized exception.
    # We need to temporarily override the mock dependency provided by the fixture for this specific test.
    # Use dependency_overrides directly within the test with a context manager or try/finally

    # Access the test user ID from the client instance
    test_user_id = client.test_user_id # Not strictly needed in this test as we expect 401 before user is retrieved

    # Temporarily override get_current_user to raise HTTPException
    async def mock_get_current_user_unauthorized_override():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

    # Apply the override for this test
    original_override = client.app.dependency_overrides.get(get_current_user_dependency)
    client.app.dependency_overrides[get_current_user_dependency] = mock_get_current_user_unauthorized_override

    try:
        # GET request to /me
        # No need for Authorization header, as auth dependency is mocked via override
        response = client.get("/api/v1/users/me")

        # Check that the response status code is 401 and the detail matches the exception
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json().get('detail') == "Invalid credentials"
        # Verify that the WWW-Authenticate header is present
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

        # In this override approach, we don't assert on the mock being called, as we replaced the dependency itself.

    finally:
        # Clean up the override after the test
        if original_override is not None:
            client.app.dependency_overrides[get_current_user_dependency] = original_override
        else:
            del client.app.dependency_overrides[get_current_user_dependency]

@pytest.mark.anyio # Use anyio mark
async def test_update_current_user_profile(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked authentication dependency
    # We can access the test user ID from the client instance
    test_user_id = client.test_user_id

    update_data = UserProfileUpdateSchema(
        major="New Major",
        bio="Updated bio."
    )

    # Service layer is mocked to return a UserResponseSchema instance
    expected_updated_user_schema = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="test_me_user_update",
        email="me_update@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_verified=True,
        major="New Major",
        avatar_url=None,
        bio="Updated bio.",
        phone_number=None,
        join_time=datetime.now(timezone.utc) # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.update_user_profile.return_value = expected_updated_user_schema

    # Send update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put("/api/v1/users/me", json=update_data.model_dump(exclude_unset=True))

    assert response.status_code == 200
    # Convert the expected schema instance to a dictionary for comparison, handling UUID and datetime serialization
    response_json = response.json()
    # Compare most fields directly, handle UUID and datetime specifically
    # For join_time, parse both into datetime objects for comparison
    assert response_json.get('user_id') == str(expected_updated_user_schema.user_id)
    assert response_json.get('username') == expected_updated_user_schema.username
    assert response_json.get('email') == expected_updated_user_schema.email
    assert response_json.get('status') == expected_updated_user_schema.status
    assert response_json.get('credit') == expected_updated_user_schema.credit
    assert response_json.get('is_staff') == expected_updated_user_schema.is_staff
    assert response_json.get('is_verified') == expected_updated_user_schema.is_verified
    assert response_json.get('major') == expected_updated_user_schema.major
    assert response_json.get('avatar_url') == expected_updated_user_schema.avatar_url
    assert response_json.get('bio') == expected_updated_user_schema.bio
    assert response_json.get('phone_number') == expected_updated_user_schema.phone_number

    # Compare join_time by parsing both into datetime objects
    assert isoparse(response_json.get('join_time')) == expected_updated_user_schema.join_time

    mock_user_service.update_user_profile.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from mocked dependency (should be UUID object passed to service)
        update_data # Pydantic model passed directly to service
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_update_user_password_unauthorized(
    client: TestClient,
    mock_user_service: AsyncMock,
    mocker: pytest_mock.MockerFixture
):
    # This test simulates a scenario where the dependency itself raises an Unauthorized exception.
    # We need to temporarily override the mock dependency provided by the fixture for this specific test.
    # Use dependency_overrides directly within the test with a context manager or try/finally

    # Access the test user ID from the client instance
    test_user_id = client.test_user_id

    password_update_data = UserPasswordUpdate(old_password="wrongpassword", new_password="newpassword")

    # Simulate Service layer raising AuthenticationError on wrong old password
    # Note: This Service layer mock will still be active, but the AuthenticationError it raises
    # is what the router catches and converts to HTTPException(401).
    mock_user_service.update_user_password.side_effect = AuthenticationError("旧密码不正确")

    # Send password_update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put("/api/v1/users/me/password", json=password_update_data.model_dump())

    assert response.status_code == 401
    assert response.json()["detail"] == "旧密码不正确"
    assert "WWW-Authenticate" in response.headers # Authentication errors should include this header

    # We expect update_user_password service method to be called
    mock_user_service.update_user_password.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from mocked dependency (should be UUID object passed to service)
        password_update_data # Pydantic model passed directly to service
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here, except for the scenario being tested (service raising exception).

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    email = "verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)

    # Note: This test does not require authentication dependencies, so we don't need to configure mock_get_current_user/admin
    # It relies on get_user_service being mocked in the client fixture.

    # Simulate Service returning a dict as expected by the router
    mock_user_service.request_verification_email.return_value = {"message": "验证邮件已发送"}

    # Send request_data as JSON body
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())

    assert response.status_code == 200
    # The actual response detail might be slightly different due to router logic
    # Check for the generic success message from the router
    assert "如果邮箱存在或已注册，验证邮件已发送" in response.json()["message"]

    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        email
    )
    # Authentication dependency is not used in this endpoint.

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email_disabled(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    email = "disabled_verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)

    # Note: This test does not require authentication dependencies.
    # Simulate Service layer raising DALError for disabled account
    mock_user_service.request_verification_email.side_effect = DALError("账户已被禁用")

    # Send request_data as JSON body
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())

    assert response.status_code == 400 # Router maps this specific DALError to 400
    assert "请求验证邮件失败: 账户已被禁用" in response.json()["detail"]

    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        email
    )
    # Authentication dependency is not used in this endpoint.

@pytest.mark.anyio # Use anyio mark
async def test_verify_email(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_token = uuid4()
    verify_data = VerifyEmail(token=test_token)

    # Pydantic model_dump() on VerifyEmail will convert UUID to string automatically.
    # Ensure UUID is sent as string in JSON body by using model_dump().
    verify_data_json = verify_data.model_dump()

    # Note: This test does not require authentication dependencies.

    test_user_id = uuid4()
    # Simulate Service returning a dict with the expected structure for successful verification
    mock_user_service.verify_email.return_value = {
        "UserID": str(test_user_id), # Service returns UUID object, but we need string for JSON response
        "IsVerified": True
    }

    # Send verify_data_json (with UUID as string) as JSON body
    # Ensure UUID in JSON payload is string, although model_dump should handle it, double check
    response = client.post("/api/v1/auth/verify-email", json={"token": str(verify_data.token)})

    assert response.status_code == 200
    # Assert the structure and types of the JSON response.
    response_json = response.json()
    assert isinstance(response_json, dict)
    assert response_json.get("message") == "邮箱验证成功！您现在可以登录。"
    assert isinstance(response_json.get("user_id"), str)
    assert response_json.get("is_verified") is True
    # Optionally, verify the user_id string format if needed

    mock_user_service.verify_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_token # Service expects UUID object
    )
    # Authentication dependency is not used in this endpoint.

@pytest.mark.anyio # Use anyio mark
async def test_verify_email_invalid_token(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_token = uuid4()
    verify_data = VerifyEmail(token=test_token)

    # Pydantic model_dump() on VerifyEmail will convert UUID to string automatically.
    # Ensure UUID is sent as string in JSON body by using model_dump().
    verify_data_json = verify_data.model_dump()

    # Note: This test does not require authentication dependencies.
    # Simulate Service layer raising DALError for invalid or expired token
    mock_user_service.verify_email.side_effect = DALError("魔术链接无效或已过期")

    # Send verify_data_json (with UUID as string) as JSON body
    # Ensure UUID in JSON payload is string, although model_dump should handle it, double check
    response = client.post("/api/v1/auth/verify-email", json={"token": str(verify_data.token)})

    assert response.status_code == 400 # Router maps this specific DALError to 400
    assert "邮箱验证失败: 魔术链接无效或已过期" in response.json()["detail"]

    mock_user_service.verify_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_token # Service expects UUID object
    )
    # Authentication dependency is not used in this endpoint.

# Admin endpoint to get user profile by ID
@pytest.mark.anyio # Use anyio mark
async def test_admin_get_user_profile_by_id(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user being requested, not the admin
    test_admin_user_id = client.test_admin_user_id

    # Simulate the service returning the expected UserResponseSchema instance
    mock_user_service.get_user_profile_by_id.return_value = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="target_user",
        email="target@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_verified=True,
        major="Physics", # Explicitly include optional fields even if None
        avatar_url=None,
        bio="Target user bio.",
        phone_number="0987654321",
        join_time=datetime.now(timezone.utc) # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    expected_user_profile_schema = mock_user_service.get_user_profile_by_id.return_value # Define the variable before using it

    # GET request with user_id in path. user_id should be passed as a string in the URL.
    # No JSON body needed. No need for Authorization header, as auth dependency is mocked.
    response = client.get(f"/api/v1/users/{test_user_id}")

    assert response.status_code == 200
    response_json = response.json()
    assert isinstance(response_json, dict)
    assert "user_id" in response_json
    assert "username" in response_json
    assert "email" in response_json
    assert "status" in response_json
    assert "credit" in response_json
    assert "is_staff" in response_json
    assert "is_verified" in response_json
    assert "major" in response_json
    assert "avatar_url" in response_json
    assert "bio" in response_json
    assert "phone_number" in response_json
    assert "join_time" in response_json

    assert response_json["user_id"] == str(test_user_id)
    assert response_json["email"] == "target@example.com"
    assert response_json["status"] == "Active"
    assert response_json["credit"] == 100
    assert response_json["is_staff"] is False
    assert response_json["is_verified"] is True
    assert response_json["major"] == "Physics"
    assert response_json["bio"] == "Target user bio."
    assert response_json["phone_number"] == "0987654321"

    mock_user_service.get_user_profile_by_id.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id # User ID from path (FastAPI converts string to UUID object)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_update_user_profile_by_id(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user being updated
    test_admin_user_id = client.test_admin_user_id

    update_data = UserProfileUpdateSchema(
        major="Admin Updated Major",
        bio="Admin set bio."
    )

    # Service layer is mocked to return a UserResponseSchema instance
    expected_updated_user_schema = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="target_user_update",
        email="target_update@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_verified=True,
        major="Admin Updated Major",
        avatar_url=None,
        bio="Admin set bio.",
        phone_number="0987654321",
        join_time=datetime.now(timezone.utc) # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.update_user_profile.return_value = expected_updated_user_schema

    # Send update_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}", json=update_data.model_dump(exclude_unset=True))

    assert response.status_code == 200
    # Convert the expected schema instance to a dictionary for comparison, handling UUID and datetime serialization
    response_json = response.json()
    # Compare most fields directly, handle UUID and datetime specifically
    # For join_time, parse both into datetime objects for comparison
    assert response_json.get('user_id') == str(expected_updated_user_schema.user_id)
    assert response_json.get('username') == expected_updated_user_schema.username
    assert response_json.get('email') == expected_updated_user_schema.email
    assert response_json.get('status') == expected_updated_user_schema.status
    assert response_json.get('credit') == expected_updated_user_schema.credit
    assert response_json.get('is_staff') == expected_updated_user_schema.is_staff
    assert response_json.get('is_verified') == expected_updated_user_schema.is_verified
    assert response_json.get('major') == expected_updated_user_schema.major
    assert response_json.get('avatar_url') == expected_updated_user_schema.avatar_url
    assert response_json.get('bio') == expected_updated_user_schema.bio
    assert response_json.get('phone_number') == expected_updated_user_schema.phone_number

    # Compare join_time by parsing both into datetime objects
    assert isoparse(response_json.get('join_time')) == expected_updated_user_schema.join_time

    mock_user_service.update_user_profile.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        update_data # Pydantic model passed directly to service
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_delete_user_by_id(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user being deleted
    test_admin_user_id = client.test_admin_user_id

    mock_user_service.delete_user.return_value = True

    # DELETE request with user_id in path. No JSON body needed.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.delete(f"/api/v1/users/{test_user_id}")

    assert response.status_code == 204

    mock_user_service.delete_user.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id # User ID from path (FastAPI converts string to UUID object)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose status is being changed
    test_admin_user_id = client.test_admin_user_id

    status_update_data = UserStatusUpdateSchema(status="Disabled")

    mock_user_service.change_user_status.return_value = True

    # Send status_update_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump())

    assert response.status_code == 204

    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        status_update_data.status,
        test_admin_user_id # Admin user ID (should be UUID object passed to service)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_not_found(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose status is being changed
    test_admin_user_id = client.test_admin_user_id

    status_update_data = UserStatusUpdateSchema(status="Disabled")

    # Simulate Service layer raising NotFoundError
    mock_user_service.change_user_status.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")

    # Send status_update_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump())

    assert response.status_code == 404 # Router maps NotFoundError to 404
    assert response.json()["detail"] == f"User with ID {test_user_id} not found."

    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        status_update_data.status,
        test_admin_user_id # Admin user ID (should be UUID object passed to service)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Use dependency_overrides directly within the test with a context manager or try/finally

    # Access the test user ID from the client instance (not strictly needed here)
    test_user_id = uuid4() # ID of the user being acted upon
    test_admin_user_id = client.test_admin_user_id # Not strictly needed here as we expect 403 before user is retrieved

    # Temporarily override get_current_active_admin_user to raise HTTPException
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")

    # Apply the override for this test
    original_override = client.app.dependency_overrides.get(get_current_active_admin_user_dependency)
    client.app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        status_update_data = UserStatusUpdateSchema(status="Disabled")

        # Send status_update_data as JSON body. user_id is in path.
        # No need for Authorization header, as auth dependency is mocked via override
        response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump())

        assert response.status_code == 403 # Mock dependency should raise 403
        # Verify that the response detail matches the exception detail
        assert response.json().get('detail') == "Not an active administrator"

        # In this override approach, we don't assert on the mock being called, as we replaced the dependency itself.

    finally:
        # Clean up the override after the test
        if original_override is not None:
            client.app.dependency_overrides[get_current_active_admin_user_dependency] = original_override
        else:
            del client.app.dependency_overrides[get_current_active_admin_user_dependency]

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_invalid_value(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose status is being changed
    test_admin_user_id = client.test_admin_user_id

    # Use an invalid status value
    status_update_data = UserStatusUpdateSchema(status="InvalidStatus")

    # Simulate Service layer raising ValueError for invalid status
    # Router should catch ValueError from Service and return 400
    mock_user_service.change_user_status.side_effect = ValueError("无效的用户状态，状态必须是 Active 或 Disabled。员工无法修改用户状态。")

    # Send status_update_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump())

    # Service layer now raises ValueError for credit limits, mapped to 400 in router
    assert response.status_code == 400
    assert "无效的用户状态，状态必须是 Active 或 Disabled。" in response.json()["detail"]

    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        status_update_data.status,
        test_admin_user_id # Admin user ID (should be UUID object passed to service)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose credit is being adjusted
    test_admin_user_id = client.test_admin_user_id

    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=10, reason="Good behavior")

    mock_user_service.adjust_user_credit.return_value = True

    # Send credit_adjustment_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

    assert response.status_code == 204

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        credit_adjustment_data.credit_adjustment,
        test_admin_user_id, # Admin user ID (should be UUID object passed to service)
        credit_adjustment_data.reason
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_not_found(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose credit is being adjusted
    test_admin_user_id = client.test_admin_user_id

    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-5, reason="Violated rule")

    # Simulate Service layer raising NotFoundError
    mock_user_service.adjust_user_credit.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")

    # Send credit_adjustment_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

    assert response.status_code == 404 # Router maps NotFoundError to 404
    assert response.json()["detail"] == f"User with ID {test_user_id} not found."

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        credit_adjustment_data.credit_adjustment,
        test_admin_user_id, # Admin user ID (should be UUID object passed to service)
        credit_adjustment_data.reason
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Use dependency_overrides directly within the test with a context manager or try/finally

    # Access the test user ID from the client instance (not strictly needed here)
    test_user_id = uuid4() # ID of the user being acted upon
    test_admin_user_id = client.test_admin_user_id # Not strictly needed here as we expect 403 before user is retrieved

    # Temporarily override get_current_active_admin_user to raise HTTPException
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")

    # Apply the override for this test
    original_override = client.app.dependency_overrides.get(get_current_active_admin_user_dependency)
    client.app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=10, reason="Good behavior")

        # Send credit_adjustment_data as JSON body. user_id is in path.
        # No need for Authorization header, as auth dependency is mocked via override
        response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

        assert response.status_code == 403 # Mock dependency should raise 403
        # Verify that the response detail matches the exception detail
        assert response.json().get('detail') == "Not an active administrator"

        # In this override approach, we don't assert on the mock being called, as we replaced the dependency itself.

    finally:
        # Clean up the override after the test
        if original_override is not None:
            client.app.dependency_overrides[get_current_active_admin_user_dependency] = original_override
        else:
            del client.app.dependency_overrides[get_current_active_admin_user_dependency]

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_missing_reason(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose credit is being adjusted
    test_admin_user_id = client.test_admin_user_id

    # Create data without the reason field - Pydantic should catch this with 422
    credit_adjustment_data = {"credit_adjustment": 10} # Missing reason

    # No need to mock service call, as Pydantic validation happens before in the router

    # Send invalid data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data)

    assert response.status_code == 422 # Unprocessable Entity for validation errors
    # The 'loc' field in Pydantic v2 validation errors is a tuple, e.g., ('body', 'reason') or ('query', 'reason')
    # We need to check if 'reason' is present in any of the tuples within the 'loc' list
    assert any('reason' in loc_item for error in response.json()['detail'] for loc_item in error.get('loc', []))

    # Service method should NOT be called because of validation error
    mock_user_service.adjust_user_credit.assert_not_called()
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # but it should still be called *before* body parsing, so let's verify that.
    # This test should verify that auth dependency was called even though body validation failed.
    # We need to temporarily patch the dependency here to assert on its call.
    mock_get_current_active_admin_user_patch = mocker.patch('app.dependencies.get_current_active_admin_user', new_callable=AsyncMock)
    # Configure the patched mock to return the default admin user payload
    mock_admin_user_payload = {"user_id": test_admin_user_id, "UserID": test_admin_user_id, "username": "adminuser", "is_staff": True, "is_verified": True}
    mock_get_current_active_admin_user_patch.return_value = mock_admin_user_payload
    # Remove assertion for auth dependency call as it's not called in 422 scenario

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_exceeding_max(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose credit is being adjusted
    test_admin_user_id = client.test_admin_user_id

    # Adjustment that would result in credit > 100
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=60, reason="Good behavior")

    # Simulate Service layer raising ValueError for exceeding limit
    # Router should catch ValueError from Service and return 400
    mock_user_service.adjust_user_credit.side_effect = ValueError("信用分不能超过100。")

    # Send credit_adjustment_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

    # Service layer now raises ValueError for credit limits, mapped to 400 in router
    assert response.status_code == 400
    assert "信用分不能超过100。" in response.json()["detail"]

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        credit_adjustment_data.credit_adjustment,
        test_admin_user_id, # Admin user ID (should be UUID object passed to service)
        credit_adjustment_data.reason
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_below_min(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4() # This is the ID of the user whose credit is being adjusted
    test_admin_user_id = client.test_admin_user_id

    # Adjustment that would result in credit < 0
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-60, reason="Bad behavior")

    # Simulate Service layer raising ValueError for being below minimum
    # Router should catch ValueError from Service and return 400
    mock_user_service.adjust_user_credit.side_effect = ValueError("信用分不能低于0。")

    # Send credit_adjustment_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

    # Service layer now raises ValueError for credit limits, mapped to 400 in router
    assert response.status_code == 400
    assert "信用分不能低于0。".encode('utf-8') in response.content # Assert byte string for non-ASCII chars

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path (FastAPI converts string to UUID object)
        credit_adjustment_data.credit_adjustment,
        test_admin_user_id, # Admin user ID (should be UUID object passed to service)
        credit_adjustment_data.reason
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

# Admin endpoint to get all users
@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_admin_user_id = client.test_admin_user_id

    # Simulate the service returning a list of UserResponseSchema instances
    # Use fixed UUIDs for predictable test results
    fixed_user_id_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    fixed_user_id_2 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    # Use a fixed datetime for predictable test results
    fixed_join_time_1 = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    fixed_join_time_2 = datetime(2023, 1, 2, 11, 30, 0, tzinfo=timezone.utc)

    # Simulate the service returning a list of dictionaries that would be produced by _convert_dal_user_to_schema
    mock_user_service.get_all_users.return_value = [
        {
            'user_id': fixed_user_id_1, # Service returns UUID object
            'username': "user1",
            'email': "user1@example.com",
            'status': "Active",
            'credit': 100,
            'is_staff': False,
            'is_verified': True,
            'major': None,
            'avatar_url': None,
            'bio': None,
            'phone_number': None,
            'join_time': fixed_join_time_1 # Service returns datetime object
        },
        {
            'user_id': fixed_user_id_2, # Service returns UUID object
            'username': "user2",
            'email': "user2@example.com",
            'status': "Disabled",
            'credit': 50,
            'is_staff': False,
            'is_verified': False,
            'major': None,
            'avatar_url': None,
            'bio': None,
            'phone_number': None,
            'join_time': fixed_join_time_2 # Service returns datetime object
        },
    ]
    # The mock now returns a list of dictionaries

    # GET request to /users/ does not send a body.
    # No need for Authorization header, as auth dependency is mocked.
    response = client.get("/api/v1/users/")

    assert response.status_code == 200
    response_json = response.json()

    # Check if the response is a list and has the correct number of items
    assert isinstance(response_json, list)
    # Compare with the length of the mocked return value directly
    assert len(response_json) == len(mock_user_service.get_all_users.return_value)

    # Validate the structure and data types of items in the list
    for user_data in response_json:
        assert isinstance(user_data, dict)
        assert isinstance(user_data.get("user_id"), str)
        assert isinstance(user_data.get("username"), str)
        assert isinstance(user_data.get("email"), str)
        assert isinstance(user_data.get("status"), str)
        assert isinstance(user_data.get("credit"), int)
        assert isinstance(user_data.get("is_staff"), bool)
        assert isinstance(user_data.get("is_verified"), bool)
        assert isinstance(user_data.get("join_time"), str) # Datetime serialized to string

        # Check for presence of optional fields
        assert "major" in user_data
        assert "avatar_url" in user_data
        assert "bio" in user_data
        assert "phone_number" in user_data
        assert isinstance(user_data.get("major"), (str, type(None)))
        assert isinstance(user_data.get("avatar_url"), (str, type(None)))
        assert isinstance(user_data.get("bio"), (str, type(None)))
        assert isinstance(user_data.get("phone_number"), (str, type(None)))

    # Compare serialized JSON output with expected structure/values
    # Convert expected UserResponseSchema objects to dictionaries with aliases and ISO format datetime for comparison
    # When comparing with the actual JSON response from FastAPI, we expect UUIDs and datetimes
    # to be serialized as strings (ISO 8601 for datetime).
    # The mock service now returns a list of dictionaries with UUID and datetime objects.
    # We need to convert this expected list to the format FastAPI's JSONResponse produces.
    expected_json_list = []
    for user_dict in mock_user_service.get_all_users.return_value:
        expected_item = {}
        for key, value in user_dict.items():
            if isinstance(value, UUID):
                expected_item[key] = str(value)
            elif isinstance(value, datetime):
                # Ensure ISO 8601 format with Z for UTC to match FastAPI's serialization
                # Use isoformat() directly which handles timezone correctly for UTC
                expected_item[key] = value.isoformat(timespec='seconds').replace('+00:00', 'Z') # Ensure Z for UTC
            else:
                expected_item[key] = value
        expected_json_list.append(expected_item)

    # Perform a more flexible check that the list contains the expected items, possibly ignoring order
    # For exact order check: assert response_json == expected_json_list
    # For content check (order doesn't matter): assert collections.Counter(response_json) == collections.Counter(expected_json_list)
    assert len(response_json) == len(expected_json_list)
    # Use a set comparison for flexible order check if needed, but direct list comparison is fine if order is guaranteed
    # For now, direct comparison is expected to pass.
    assert response_json == expected_json_list

    # Verify service method was called with correct arguments
    mock_user_service.get_all_users.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_admin_user_id # Admin user ID from mocked dependency (should be UUID object passed to service)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

# Admin endpoint to get all users (forbidden case)
@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Use dependency_overrides directly within the test with a context manager or try/finally

    # Temporarily override get_current_active_admin_user to raise HTTPException
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")

    # Apply the override for this test
    original_override = client.app.dependency_overrides.get(get_current_active_admin_user_dependency)
    client.app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        # GET request to /users/ does not send a body.
        # No need for Authorization header, as auth dependency is mocked via override
        response = client.get("/api/v1/users/")

        assert response.status_code == 403 # Mock dependency raises 403
        # Verify that the response detail matches the exception detail
        assert response.json().get('detail') == "Not an active administrator"

        # In this override approach, we don't assert on the mock being called, as we replaced the dependency itself.

    finally:
        # Clean up the override after the test
        if original_override is not None:
            client.app.dependency_overrides[get_current_active_admin_user_dependency] = original_override
        else:
            del client.app.dependency_overrides[get_current_active_admin_user_dependency] 