# tests/test_users_api.py
import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from unittest.mock import AsyncMock # Import AsyncMock for mocking async methods
from fastapi import Depends, status, HTTPException # Import HTTPException
import pytest_mock
from unittest.mock import MagicMock
from unittest.mock import patch
from app.dal.connection import get_db_connection # Import the actual dependency function

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
from app.services.user_service import UserService
# Import dependencies file where get_user_service is defined
from app.dependencies import get_user_service, get_current_user, get_current_active_admin_user, get_db_conn # Import get_db_conn
from app.dal.user_dal import UserDAL # Import UserDAL for type hinting

from datetime import datetime # Import datetime

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

@pytest.fixture(scope="function")
def client(mock_user_service, mock_auth_dependencies, mocker):
    # Use app.dependency_overrides to mock dependencies for the TestClient
    # Mock the get_db_connection dependency in app.dal.connection
    async def override_get_db_connection_async(): # Define the async override function
        # Return a mock connection object
        mock_conn = MagicMock()
        yield mock_conn # Yield the mock connection asynchronously

    print(f"DEBUG: TestClient using app instance with id: {id(app)}")
    print(f"DEBUG: App routes in TestClient: {app.routes}")

    # Set up dependency overrides
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[get_current_user] = mock_auth_dependencies[0] # Use the mocked get_current_user
    app.dependency_overrides[get_current_active_admin_user] = mock_auth_dependencies[1] # Use the mocked get_current_active_admin_user
    # Override the actual get_db_connection in app.dal.connection
    app.dependency_overrides[get_db_connection] = override_get_db_connection_async

    with TestClient(app) as tc:
        yield tc

    # Clean up the dependency override after the test is done
    app.dependency_overrides.clear()

# Remove the clean_db fixture as we are mocking the DAL/Service
# @pytest.fixture(scope="function", autouse=True)
# async def clean_db():
# ... removed ...
# --- End Test Fixtures ---

# --- Mock Fixture for UserService --- (New)
@pytest.fixture
def mock_user_service(mocker):
    """Mock the UserService dependency."""
    # Create an AsyncMock instance for the UserService class
    mock_service = AsyncMock(spec=UserService)
    # Patch the get_user_service dependency to return our mock service instance
    mocker.patch('app.dependencies.get_user_service', return_value=mock_service)
    return mock_service

# --- Mock Fixture for Authentication Dependencies --- (New)
# Mock get_current_user and get_current_active_admin_user
@pytest.fixture
def mock_auth_dependencies(mocker):
    mock_get_current_user = mocker.patch('app.dependencies.get_current_user', new_callable=AsyncMock)
    mock_get_current_active_admin_user = mocker.patch('app.dependencies.get_current_active_admin_user', new_callable=AsyncMock)
    return mock_get_current_user, mock_get_current_active_admin_user

# --- Mock Fixture for Database Connection Dependency --- (New)
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
    # Ensure keys match UserResponseSchema and date format is string
    expected_created_user = {
        "user_id": uuid4(), # Simulate a generated UUID (Service returns UUID object)
        "username": username,
        "email": email,
        "status": "Active",
        "credit": 100,
        "is_staff": False,
        "is_verified": False,
        "major": None,
        "avatar_url": None,
        "bio": None,
        "phone_number": None,
        "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    mock_user_service.create_user.return_value = expected_created_user
    
    response = client.post("/api/v1/auth/register", json=user_data.model_dump())
    
    assert response.status_code == 201
    created_user = response.json()
    # In API test, compare against serialized JSON. Pydantic will serialize UUID and datetime.
    assert created_user["user_id"] == str(expected_created_user["user_id"])
    assert created_user["username"] == expected_created_user["username"]
    assert created_user["email"] == expected_created_user["email"]
    assert created_user["status"] == expected_created_user["status"]
    assert created_user["credit"] == expected_created_user["credit"]
    assert created_user["is_staff"] == expected_created_user["is_staff"]
    assert created_user["is_verified"] == expected_created_user["is_verified"]
    assert created_user["major"] == expected_created_user["major"]
    assert created_user["avatar_url"] == expected_created_user["avatar_url"]
    assert created_user["bio"] == expected_created_user["bio"]
    assert created_user["phone_number"] == expected_created_user["phone_number"]
    # FastAPI/Pydantic serializes datetime to ISO 8601 string by default
    assert created_user["join_time"] == expected_created_user["join_time"].isoformat()
    
    # Verify that the service method was called with the correct arguments
    # The first argument is the database connection, which is injected by FastAPI/Depends
    # We can use mocker.ANY to ignore the connection object
    mock_user_service.create_user.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
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
        mocker.ANY,
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
        mocker.ANY,
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
    response = client.post("/api/v1/auth/login", data=login_data.model_dump())

    assert response.status_code == 200
    token_data = response.json()
    assert token_data["access_token"] == expected_token
    assert token_data["token_type"] == "bearer"
    
    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
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

    response = client.post("/api/v1/auth/login", data=login_data.model_dump())

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码不正确"
    assert "WWW-Authenticate" in response.headers
    
    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY,
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

    response = client.post("/api/v1/auth/login", data=login_data.model_dump())

    assert response.status_code == 403 # Or 401 depending on exact API design/exception handling
    assert response.json()["detail"] == "账户已被禁用"
    
    mock_user_service.authenticate_user_and_create_token.assert_called_once_with(
        mocker.ANY,
        username,
        password
    )

@pytest.mark.anyio # Use anyio mark
async def test_read_users_me(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_user dependency to return a mock user dict
    mock_auth_dependencies[0].return_value = {"UserID": test_user_id, "username": "test_me_user", "is_staff": False, "is_verified": True}
    
    # Define the expected return value from the mocked service method
    # Ensure keys match UserResponseSchema and date format is string
    expected_user_profile = {
        "user_id": test_user_id, # Simulate UUID object from Service
        "username": "test_me_user",
        "email": "me@example.com",
        "status": "Active",
        "credit": 100,
        "is_staff": False,
        "is_verified": True,
        "major": "CS",
        "avatar_url": None,
        "bio": "Test bio.",
        "phone_number": "1234567890",
        "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    mock_user_service.get_user_profile_by_id.return_value = expected_user_profile
    
    # No need for a real token, the dependency is mocked
    response = client.get("/api/v1/users/me")
    
    assert response.status_code == 200
    # Compare against serialized JSON response
    assert response.json()["user_id"] == str(expected_user_profile["user_id"])
    assert response.json()["username"] == expected_user_profile["username"]
    assert response.json()["email"] == expected_user_profile["email"]
    assert response.json()["status"] == expected_user_profile["status"]
    assert response.json()["credit"] == expected_user_profile["credit"]
    assert response.json()["is_staff"] == expected_user_profile["is_staff"]
    assert response.json()["is_verified"] == expected_user_profile["is_verified"]
    assert response.json()["major"] == expected_user_profile["major"]
    assert response.json()["avatar_url"] == expected_user_profile["avatar_url"]
    assert response.json()["bio"] == expected_user_profile["bio"]
    assert response.json()["phone_number"] == expected_user_profile["phone_number"]
    assert response.json()["join_time"] == expected_user_profile["join_time"].isoformat()
    
    # Verify that the service method was called with the correct arguments
    mock_user_service.get_user_profile_by_id.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id # User ID from the mocked dependency
    )
    
    # Verify that get_current_user was called
    mock_auth_dependencies[0].assert_called_once_with(mocker.ANY) # Pass mocker.ANY for the token dependency

@pytest.mark.anyio # Use anyio mark
async def test_read_users_me_unauthorized(client: TestClient, mock_auth_dependencies, mocker):
    # Simulate get_current_user raising an exception (e.g., InvalidCredentialsException or just HTTPException)
    mock_auth_dependencies[0].side_effect = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") # Simulate auth failure
    
    response = client.get("/api/v1/users/me")
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    
    # Verify that the service method was NOT called
    # mock_user_service.get_user_profile_by_id.assert_not_called()
    # Verify that get_current_user was called
    mock_auth_dependencies[0].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_update_current_user_profile(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_user dependency
    mock_auth_dependencies[0].return_value = {"UserID": test_user_id, "username": "test_me_user_update", "is_staff": False, "is_verified": True}
    
    update_data = UserProfileUpdateSchema(
        major="New Major",
        bio="Updated bio."
    )
    
    # Define the expected return value from the mocked service method
    # Ensure keys match UserResponseSchema and date format is string
    expected_updated_user = {
        "user_id": str(test_user_id),
        "username": "test_me_user_update",
        "email": "me_update@example.com",
        "status": "Active",
        "credit": 100,
        "is_staff": False,
        "is_verified": True,
        "major": "New Major",
        "avatar_url": None,
        "bio": "Updated bio.",
        "phone_number": None,
        "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    mock_user_service.update_user_profile.return_value = expected_updated_user
    
    response = client.put("/api/v1/users/me", json=update_data.model_dump(exclude_unset=True))
    
    assert response.status_code == 200
    assert response.json() == expected_updated_user
    
    mock_user_service.update_user_profile.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from the mocked dependency
        update_data # Pydantic model passed directly
    )
    mock_auth_dependencies[0].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_update_user_password_unauthorized(
    client: TestClient,
    mock_user_service: AsyncMock,
    mock_auth_dependencies,
    mocker: pytest_mock.MockerFixture
):
    """Service layer test for updating password with incorrect old password."""
    test_user_id = uuid4()
    # Configure the mocked get_current_user dependency
    # Use mock_auth_dependencies for get_current_user mock
    mock_auth_dependencies[0].return_value = {"UserID": test_user_id, "username": "test_me_user_pass_unauth", "is_staff": False, "is_verified": True}

    password_update_data = UserPasswordUpdate(old_password="wrongpassword", new_password="newpassword")

    # Simulate Service layer raising AuthenticationError for incorrect old password
    mock_user_service.update_user_password.side_effect = AuthenticationError("旧密码不正确")

    response = client.put("/api/v1/users/me/password", json=password_update_data.model_dump())

    assert response.status_code == 401
    assert response.json()["detail"] == "旧密码不正确"

    # Assert Service method was called with correct arguments
    # Use mocker.ANY for the database connection parameter
    mock_user_service.update_user_password.assert_called_once_with(
        mocker.ANY, # Use mocker.ANY for the mocked DB connection
        test_user_id,
        password_update_data
    )
    # Verify the correct authentication dependency was called
    mock_auth_dependencies[0].assert_called_once_with(mocker.ANY) # Verify get_current_user was called

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email(client: TestClient, mock_user_service: AsyncMock, mocker):
    email = "verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)
    
    # Simulate Service layer returning success result (or None if function signature changes)
    # Ensure keys match expected response
    mock_user_service.request_verification_email.return_value = {"message": "验证邮件已发送"}
    
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())
    
    assert response.status_code == 200
    assert "验证邮件已发送" in response.json()["message"]
    
    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY,
        email
    )

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email_disabled(client: TestClient, mock_user_service: AsyncMock, mocker):
    email = "disabled_verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)
    
    # Simulate Service layer raising DALError for disabled account
    mock_user_service.request_verification_email.side_effect = DALError("账户已被禁用")
    
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())
    
    assert response.status_code == 400
    assert "账户已被禁用" in response.json()["detail"]
    
    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY,
        email
    )

@pytest.mark.anyio # Use anyio mark
async def test_verify_email(client: TestClient, mock_user_service: AsyncMock, mocker):
    test_token = uuid4()
    verify_data = VerifyEmail(token=test_token)
    
    # Manually convert UUID to string for JSON serialization for the request body
    verify_data_json = verify_data.model_dump()
    verify_data_json['token'] = str(verify_data_json['token'])

    # Simulate Service layer returning success result
    # Service verify_email should return a dict with 'UserID' and 'IsVerified' based on Service implementation.
    # The router expects this structure and constructs the final response body.
    # Let's simulate the Service return that matches the Service method definition.
    mock_user_service.verify_email.return_value = {
        "UserID": uuid4(), # Simulate UUID object from Service
        "IsVerified": True
    }
    
    response = client.post("/api/v1/auth/verify-email", json=verify_data_json)
    
    assert response.status_code == 200
    # The router should return a dict like {"message": "...", "is_verified": ...}
    assert "邮箱验证成功" in response.json()["message"]
    assert response.json()["is_verified"] is True
    
    mock_user_service.verify_email.assert_called_once_with(
        mocker.ANY,
        test_token
    )

@pytest.mark.anyio # Use anyio mark
async def test_verify_email_invalid_token(client: TestClient, mock_user_service: AsyncMock, mocker):
    test_token = uuid4()
    verify_data = VerifyEmail(token=test_token)
    
    # Manually convert UUID to string for JSON serialization
    verify_data_json = verify_data.model_dump()
    verify_data_json['token'] = str(verify_data_json['token'])

    # Simulate Service layer raising DALError for invalid/expired token
    mock_user_service.verify_email.side_effect = DALError("魔术链接无效或已过期")

    response = client.post("/api/v1/auth/verify-email", json=verify_data_json)
    
    assert response.status_code == 400
    assert "邮箱验证失败: 魔术链接无效或已过期" in response.json()["detail"]
    
    mock_user_service.verify_email.assert_called_once_with(
        mocker.ANY,
        test_token
    )

@pytest.mark.anyio # Use anyio mark
async def test_admin_get_user_profile_by_id(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    
    # Define the expected return value from the mocked service method
    # Ensure keys match UserResponseSchema and date format is string
    expected_user_profile = {
        "user_id": test_user_id, # Simulate UUID object from Service
        "username": "target_user",
        "email": "target@example.com",
        "status": "Active",
        "credit": 100,
        "is_staff": False,
        "is_verified": True,
        "major": "Physics",
        "avatar_url": None,
        "bio": "Target user bio.",
        "phone_number": "0987654321",
        "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    mock_user_service.get_user_profile_by_id.return_value = expected_user_profile
    
    response = client.get(f"/api/v1/users/{test_user_id}", headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 200
    # Compare against serialized JSON response
    assert response.json()["user_id"] == str(expected_user_profile["user_id"])
    assert response.json()["username"] == expected_user_profile["username"]
    assert response.json()["email"] == expected_user_profile["email"]
    assert response.json()["status"] == expected_user_profile["status"]
    assert response.json()["credit"] == expected_user_profile["credit"]
    assert response.json()["is_staff"] == expected_user_profile["is_staff"]
    assert response.json()["is_verified"] == expected_user_profile["is_verified"]
    assert response.json()["major"] == expected_user_profile["major"]
    assert response.json()["avatar_url"] == expected_user_profile["avatar_url"]
    assert response.json()["bio"] == expected_user_profile["bio"]
    assert response.json()["phone_number"] == expected_user_profile["phone_number"]
    assert response.json()["join_time"] == expected_user_profile["join_time"].isoformat()
    
    mock_user_service.get_user_profile_by_id.assert_called_once_with(
        mocker.ANY,
        test_user_id
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY) # Verify admin dependency was called

@pytest.mark.anyio # Use anyio mark
async def test_admin_update_user_profile_by_id(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user_update", "is_staff": True}
    
    update_data = UserProfileUpdateSchema(
        major="Admin Updated Major",
        bio="Admin set bio."
    )
    
    # Define the expected return value from the mocked service method
    # Ensure keys match UserResponseSchema and date format is string
    expected_updated_user = {
        "user_id": test_user_id, # Simulate UUID object from Service
        "username": "target_user_update",
        "email": "target_update@example.com",
        "status": "Active",
        "credit": 100,
        "is_staff": False,
        "is_verified": True,
        "major": "Admin Updated Major",
        "avatar_url": None,
        "bio": "Admin set bio.",
        "phone_number": "0987654321",
        "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    mock_user_service.update_user_profile.return_value = expected_updated_user
    
    response = client.put(f"/api/v1/users/{test_user_id}", json=update_data.model_dump(exclude_unset=True), headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 200
    # Compare against serialized JSON response
    assert response.json()["user_id"] == str(expected_updated_user["user_id"])
    assert response.json()["username"] == expected_updated_user["username"]
    assert response.json()["email"] == expected_updated_user["email"]
    assert response.json()["status"] == expected_updated_user["status"]
    assert response.json()["credit"] == expected_updated_user["credit"]
    assert response.json()["is_staff"] == expected_updated_user["is_staff"]
    assert response.json()["is_verified"] == expected_updated_user["is_verified"]
    assert response.json()["major"] == expected_updated_user["major"]
    assert response.json()["avatar_url"] == expected_updated_user["avatar_url"]
    assert response.json()["bio"] == expected_updated_user["bio"]
    assert response.json()["phone_number"] == expected_updated_user["phone_number"]
    assert response.json()["join_time"] == expected_updated_user["join_time"].isoformat()
    
    mock_user_service.update_user_profile.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        update_data
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_delete_user_by_id(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user_delete", "is_staff": True}
    
    # Simulate Service layer returning True on successful deletion
    mock_user_service.delete_user.return_value = True
    
    response = client.delete(f"/api/v1/users/{test_user_id}", headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 204
    
    mock_user_service.delete_user.assert_called_once_with(
        mocker.ANY,
        test_user_id
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_delete_user_by_id_not_found(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user_delete_notfound", "is_staff": True}
    
    # Simulate Service layer raising NotFoundError
    mock_user_service.delete_user.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")
    
    response = client.delete(f"/api/v1/users/{test_user_id}", headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 404
    assert response.json()["detail"] == f"User with ID {test_user_id} not found."
    
    mock_user_service.delete_user.assert_called_once_with(
        mocker.ANY,
        test_user_id
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

# TODO: Add tests for edge cases and other potential API endpoints (e.g., admin list users)

# TODO: If login should require verification, modify the router and add a test here for 403 Forbidden.
# TODO: Add tests for other potential admin endpoints (e.g., getting all users, disabling/enabling accounts via new endpoints if added)

# --- New Admin API Tests ---

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_success(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    
    status_update_data = UserStatusUpdateSchema(status="Disabled")
    
    # Simulate Service layer returning True on successful status change
    mock_user_service.change_user_status.return_value = True
    
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 204
    
    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path
        status_update_data.status, # Status from request body
        mocker.ANY # Admin user ID from dependency
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY) # Verify admin dependency was called

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_not_found(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    status_update_data = UserStatusUpdateSchema(status="Disabled")

    # Simulate Service layer raising NotFoundError
    mock_user_service.change_user_status.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")

    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 404
    assert response.json()["detail"] == f"User with ID {test_user_id} not found."
    
    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        status_update_data.status,
        mocker.ANY
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_forbidden(client: TestClient, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Simulate get_current_active_admin_user raising ForbiddenError (e.g., not an admin)
    mock_auth_dependencies[1].side_effect = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")
    status_update_data = UserStatusUpdateSchema(status="Disabled")

    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump(), headers={'Authorization': 'Bearer regular_user_token'})

    assert response.status_code == 403
    assert response.json()["detail"] == "Not an active administrator"
    
    # Service method should NOT be called
    # mock_user_service.change_user_status.assert_not_called()
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

# TODO: Add test for invalid status value (FastAPI validation or Service/DAL error)

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_invalid_value(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    # Use an invalid status value
    status_update_data = UserStatusUpdateSchema(status="InvalidStatus")

    # Simulate Service layer raising DALError for invalid status
    mock_user_service.change_user_status.side_effect = DALError("无效的用户状态，状态必须是 Active 或 Disabled。")

    response = client.put(f"/api/v1/users/{test_user_id}/status", json=status_update_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 400 # Assuming DALError maps to 400
    assert "无效的用户状态，状态必须是 Active 或 Disabled。" in response.json()["detail"]

    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        status_update_data.status,
        mocker.ANY
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_success(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=10, reason="Good behavior")
    
    # Simulate Service layer returning True on successful adjustment
    mock_user_service.adjust_user_credit.return_value = True
    
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})
    
    assert response.status_code == 204
    
    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path
        credit_adjustment_data.credit_adjustment, # Adjustment from request body
        mocker.ANY, # Admin user ID from dependency
        credit_adjustment_data.reason # Reason from request body
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_not_found(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-5, reason="Violated rule")

    # Simulate Service layer raising NotFoundError
    mock_user_service.adjust_user_credit.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")

    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 404
    assert response.json()["detail"] == f"User with ID {test_user_id} not found."
    
    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        credit_adjustment_data.credit_adjustment,
        mocker.ANY,
        credit_adjustment_data.reason
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_forbidden(client: TestClient, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].side_effect = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=10, reason="Good behavior")

    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump(), headers={'Authorization': 'Bearer regular_user_token'})

    assert response.status_code == 403
    assert response.json()["detail"] == "Not an active administrator"
    
    # Service method should NOT be called
    # mock_user_service.adjust_user_credit.assert_not_called()
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

# New test for missing reason
@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_missing_reason(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True} # This line is actually not reached in case of 422, but keep it for consistency if we change the test
    # Create data without the reason field - Pydantic should catch this
    credit_adjustment_data = {"credit_adjustment": 10} # Missing reason

    # No need to mock service call, as Pydantic validation happens before

    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data, headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 422 # Unprocessable Entity for validation errors
    # The 'loc' field in Pydantic v2 validation errors is a tuple, e.g., ('body', 'reason') or ('query', 'reason')
    # We need to check if 'reason' is present in any of the tuples within the 'loc' list
    assert any('reason' in loc_item for error in response.json()['detail'] for loc_item in error.get('loc', []))

    # Service method should NOT be called
    mock_user_service.adjust_user_credit.assert_not_called()
    # Remove the assertion that the dependency was called
    # mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)


# New test for credit adjustment exceeding limit (e.g., > 100)
@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_exceeding_max(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    # Adjustment that would result in credit > 100
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=60, reason="Good behavior")

    # Simulate Service layer raising a DALError or other business error for exceeding limit
    # Assuming Service maps DAL error to a specific message or raises its own error
    mock_user_service.adjust_user_credit.side_effect = DALError("信用分不能超过100。") # Simulate DAL/SP error message

    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 400 # Or 422 depending on how this specific error is handled
    assert "信用分不能超过100。" in response.json()["detail"]

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        credit_adjustment_data.credit_adjustment,
        mocker.ANY,
        credit_adjustment_data.reason
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

# New test for credit adjustment below minimum (e.g., < 0)
@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_below_min(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_user_id = uuid4()
    mock_auth_dependencies[1].return_value = {"UserID": uuid4(), "username": "admin_user", "is_staff": True}
    # Adjustment that would result in credit < 0
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-60, reason="Bad behavior")

    # Simulate Service layer raising a DALError or other business error for being below minimum
    mock_user_service.adjust_user_credit.side_effect = DALError("信用分不能低于0。") # Simulate DAL/SP error message

    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump(), headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 400 # Or 422 depending on how this specific error is handled
    assert "信用分不能低于0。" in response.json()["detail"]

    mock_user_service.adjust_user_credit.assert_called_once_with(
        mocker.ANY,
        test_user_id,
        credit_adjustment_data.credit_adjustment,
        mocker.ANY,
        credit_adjustment_data.reason
    )
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY)

# TODO: Add tests for other potential admin endpoints (e.g., getting all users, disabling/enabling accounts via new endpoints if added)

# Admin endpoint to get all users
@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_success(client: TestClient, mock_user_service: AsyncMock, mock_auth_dependencies, mocker):
    test_admin_id = uuid4()
    # Configure the mocked get_current_active_admin_user dependency
    mock_auth_dependencies[1].return_value = {"UserID": test_admin_id, "username": "admin_user", "is_staff": True}

    # Define the expected return value from the mocked service method
    # Ensure keys match UserResponseSchema and date format is string
    expected_users_list = [
        {
            "user_id": uuid4(), # Simulate UUID object from Service
            "username": "user1",
            "email": "user1@example.com",
            "status": "Active",
            "credit": 100,
            "is_staff": False,
            "is_verified": True,
            "major": "CS",
            "avatar_url": None,
            "bio": "User 1 bio.",
            "phone_number": "1111111111",
            "join_time": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
        },
        {
            "user_id": uuid4(), # Simulate UUID object from Service
            "username": "user2",
            "email": "user2@example.com",
            "status": "Disabled",
            "credit": 50,
            "is_staff": False,
            "is_verified": False,
            "major": None,
            "avatar_url": None,
            "bio": None,
            "phone_number": None,
            "join_time": datetime(2023, 1, 2, 12, 0, 0) # Simulate datetime object
        }
    ]
    mock_user_service.get_all_users.return_value = expected_users_list

    response = client.get("/api/v1/users/", headers={'Authorization': 'Bearer admin_token'})

    assert response.status_code == 200
    users_list = response.json()
    # Compare against serialized JSON response
    assert len(users_list) == len(expected_users_list)
    for i in range(len(users_list)):
        assert users_list[i]["user_id"] == str(expected_users_list[i]["user_id"])
        assert users_list[i]["username"] == expected_users_list[i]["username"]
        assert users_list[i]["email"] == expected_users_list[i]["email"]
        assert users_list[i]["status"] == expected_users_list[i]["status"]
        assert users_list[i]["credit"] == expected_users_list[i]["credit"]
        assert users_list[i]["is_staff"] == expected_users_list[i]["is_staff"]
        assert users_list[i]["is_verified"] == expected_users_list[i]["is_verified"]
        assert users_list[i]["major"] == expected_users_list[i]["major"]
        assert users_list[i]["avatar_url"] == expected_users_list[i]["avatar_url"]
        assert users_list[i]["bio"] == expected_users_list[i]["bio"]
        assert users_list[i]["phone_number"] == expected_users_list[i]["phone_number"]
        assert users_list[i]["join_time"] == expected_users_list[i]["join_time"].isoformat()

    # Verify that the service method was called with the correct arguments
    mock_user_service.get_all_users.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_admin_id # Admin user ID from dependency
    )

@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_forbidden(client: TestClient, mock_auth_dependencies, mocker):
    """Test admin get all users fails due to lack of admin permission."""
    # Simulate get_current_active_admin_user raising ForbiddenError for non-admin
    mock_auth_dependencies[1].side_effect = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an active administrator")

    # No need to mock service layer, as the dependency will raise the exception first

    response = client.get("/api/v1/users/", headers={'Authorization': 'Bearer regular_user_token'})

    assert response.status_code == 403
    assert response.json()["detail"] == "Not an active administrator"

    # Service method should NOT be called
    # mock_user_service.get_all_users.assert_not_called()
    mock_auth_dependencies[1].assert_called_once_with(mocker.ANY) 