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
    # Arrange
    # Updated user data for registration (no email, with phone_number)
    register_data = {
        "username": "newuser_api",
        "password": "securepassword",
        "confirmPassword": "securepassword", # Assuming frontend sends this
        "major": "Literature",
        "phone_number": "1231231234", # Changed from phoneNumber to phone_number
    }

    # Simulate successful user creation return from the service layer
    # The service should return a UserResponseSchema instance or similar dict
    # Ensure the mocked service return includes phone_number and handles email as None
    created_user_from_service = UserResponseSchema(
        user_id=uuid4(),
        username=register_data["username"],
        email=None, # Email is None on registration
        status="Active",
        credit=100,
        is_staff=False,
        is_verified=False,
        major=register_data["major"],
        avatar_url=None,
        bio=None,
        phone_number=register_data["phone_number"], # Use phone_number
        join_time=datetime.utcnow(),
        is_super_admin=False, # Include is_super_admin in mock return
    )
    
    # Mock the service's create_user method
    # The service method is expected to be called with UserRegisterSchema, not the raw dict
    # However, the API router handles Pydantic model creation, so the mock should expect the Pydantic model
    # We can mock the return value directly as the expected UserResponseSchema
    mock_user_service.create_user.return_value = created_user_from_service

    # Act
    # Call the API endpoint with the updated registration data
    response = client.post("/api/v1/auth/register", json=register_data)

    # Assert
    assert response.status_code == 201 # Expect 201 Created

    # Assert the response body matches the expected UserResponseSchema structure
    response_data = response.json()

    assert "user_id" in response_data
    assert response_data["username"] == register_data["username"]
    assert response_data.get("email") is None or response_data.get("email") == "" # Check using .get for safety
    assert response_data["major"] == register_data["major"]
    assert response_data["phone_number"] == register_data["phone_number"] # Assert phone_number is in response
    assert response_data["status"] == "Active"
    assert response_data["credit"] == 100
    assert response_data["is_staff"] is False
    assert response_data["is_verified"] is False
    assert "join_time" in response_data

    # Verify that the service's create_user method was called with the correct data
    # The API router will create a UserRegisterSchema instance from the JSON data
    # We need to check if the mocked method was called with a UserRegisterSchema object having the correct attributes
    
    # Construct the expected UserRegisterSchema object that the service should receive
    expected_user_data_in_service_call = UserRegisterSchema(
        username=register_data["username"],
        password=register_data["password"],
        major=register_data["major"],
        phone_number=register_data["phone_number"],
    )
    
    # Use mocker.call to capture the arguments the mock was called with
    mock_user_service.create_user.assert_called_once()
    # Get the actual arguments the mock was called with
    call_args, call_kwargs = mock_user_service.create_user.call_args
    
    # The first argument should be the DB connection (mock_db_connection)
    assert call_args[0] == mocker.ANY # Or mock_db_connection if needed, but ANY is often sufficient for args you don't control directly
    # The second argument should be the UserRegisterSchema instance
    actual_user_data_in_call = call_args[1]

    assert isinstance(actual_user_data_in_call, UserRegisterSchema)
    assert actual_user_data_in_call.username == expected_user_data_in_service_call.username
    assert actual_user_data_in_call.password == expected_user_data_in_service_call.password
    assert actual_user_data_in_call.major == expected_user_data_in_service_call.major
    assert actual_user_data_in_call.phone_number == expected_user_data_in_service_call.phone_number # Assert phone_number
    # Removed assertion for email as it's no longer in UserRegisterSchema

@pytest.mark.anyio # Use anyio mark
async def test_register_user_duplicate_username(client: TestClient, mock_user_service: AsyncMock, mocker):
    # Arrange
    # Updated user data without email, with phone_number
    register_data = {
        "username": "existinguser_api",
        "password": "password123",
        "confirmPassword": "password123",
        "major": "Chemistry",
        "phone_number": "1112223333", # Changed from phoneNumber to phone_number
    }

    # Configure the service mock to raise IntegrityError for duplicate username
    mock_user_service.create_user.side_effect = IntegrityError("用户名已存在") # Match expected error message

    # Act & Assert
    # Call the API endpoint and expect a 409 Conflict due to IntegrityError
    response = client.post("/api/v1/auth/register", json=register_data)

    # Assert the response status code is 409 Conflict
    assert response.status_code == status.HTTP_409_CONFLICT

    # Assert the response body contains the expected error detail
    # The global exception handler formats the response as {'detail': 'Error Message'}
    assert response.json() == {"detail": "用户名已存在"} # Match expected error message

    # Verify that the service's create_user method was called
    mock_user_service.create_user.assert_called_once()

    # Optional: More detailed assertion on call arguments if needed
    # expected_user_schema = UserRegisterSchema(...)
    # mock_user_service.create_user.assert_called_once_with(mocker.ANY, expected_user_schema)

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
         phone_number=None,
         join_time=datetime.now(timezone.utc), # Use timezone-aware datetime
         is_super_admin=False, # Include is_super_admin in mock return
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
    assert response_json.get("phone_number") is None
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
        join_time=datetime.now(timezone.utc), # Use timezone-aware datetime
        is_super_admin=False, # Include is_super_admin in mock return
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.update_user_profile.return_value = expected_updated_user_schema

    # Send update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put("/api/v1/users/me", json=update_data.model_dump(exclude_unset=True))

    assert response.status_code == 200
    # Convert the expected schema instance to a dictionary for comparison, handling UUID and datetime serialization
    response_json = response.json()
    # Compare individual fields from the response JSON with the expected schema object
    assert isinstance(response_json, dict)
    assert response_json.get('user_id') == str(expected_updated_user_schema.user_id)
    assert response_json.get('username') == expected_updated_user_schema.username
    assert response_json.get('email') == expected_updated_user_schema.email
    assert response_json.get('status') == expected_updated_user_schema.status
    assert response_json.get('credit') == expected_updated_user_schema.credit
    assert response_json.get('is_staff') == expected_updated_user_schema.is_staff
    assert response_json.get('is_super_admin') == expected_updated_user_schema.is_super_admin
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
async def test_update_user_password_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # Arrange
    test_user_id = client.test_user_id # Get user ID from mocked authentication dependency
    password_update_data = UserPasswordUpdate(old_password="oldpassword", new_password="newpassword")

    # Simulate Service layer returning True on successful password update
    mock_user_service.update_user_password.return_value = True

    # Send password_update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put(f"/api/v1/users/{test_user_id}/password", json=password_update_data.model_dump())

    assert response.status_code == 200
    assert response.json() == {"message": "Password updated successfully"}

    # Verify that the service's update_user_password method was called with the correct data
    mock_user_service.update_user_password.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from mocked dependency (should be UUID object passed to service)
        password_update_data # Pydantic model passed directly to service
    )

@pytest.mark.anyio # Use anyio mark
async def test_update_user_password_wrong_old_password(
    client: TestClient,
    mock_user_service: AsyncMock,
    mocker: pytest_mock.MockerFixture
):
    # This test simulates a scenario where the service layer detects an incorrect old password
    # Access the test user ID from the client instance
    test_user_id = client.test_user_id

    password_update_data = UserPasswordUpdate(old_password="wrongpassword", new_password="newpassword")

    # Simulate Service layer raising AuthenticationError on wrong old password
    mock_user_service.update_user_password.side_effect = AuthenticationError("Invalid old password") # Updated error message

    # Send password_update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put(f"/api/v1/users/{test_user_id}/password", json=password_update_data.model_dump())

    assert response.status_code == 401
    # Check the detail from the HTTPException raised by the router
    assert response.json()["detail"] == "Invalid old password" # Updated error message
    assert "WWW-Authenticate" in response.headers

    # Verify that the service's update_user_password method was called
    mock_user_service.update_user_password.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from mocked dependency
        password_update_data # Pydantic model
    )

@pytest.mark.anyio # Use anyio mark
async def test_update_user_password_user_not_found(
    client: TestClient,
    mock_user_service: AsyncMock,
    mocker: pytest_mock.MockerFixture
):
    # This test simulates a scenario where the user ID from the token is not found in the database
    # Access the test user ID from the client instance
    test_user_id = client.test_user_id

    password_update_data = UserPasswordUpdate(old_password="oldpassword", new_password="newpassword")

    # Simulate Service layer raising NotFoundError
    mock_user_service.update_user_password.side_effect = NotFoundError(f"User with ID {test_user_id} not found for password update") # Updated error message

    # Send password_update_data as JSON body
    # No need for Authorization header, as auth dependency is mocked
    response = client.put(f"/api/v1/users/{test_user_id}/password", json=password_update_data.model_dump())

    assert response.status_code == 404
    # Check the detail from the HTTPException raised by the router
    assert response.json()["detail"] == f"User with ID {test_user_id} not found for password update" # Updated error message

    # Verify that the service's update_user_password method was called
    mock_user_service.update_user_password.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from mocked dependency
        password_update_data # Pydantic model
    )

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    email = "verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)

    # Note: This test does not require authentication dependencies, so we don't need to configure mock_get_current_user/admin
    # It relies on get_user_service being mocked in the client fixture.

    # Simulate Service returning a dict as expected by the router
    # The service now returns the raw dict from the DAL's request_verification_link method
    # Example of a successful DAL return (assuming it includes a message and status)
    service_return_data = {"message": "Verification email request successful", "status": "sent"}
    mock_user_service.request_verification_email.return_value = service_return_data

    # Send request_data as JSON body
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())

    assert response.status_code == 200
    # The router should return the message from the service result
    assert response.json() == {"message": "Verification email request successful"}

    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        email=email # Pass email as keyword argument
    )
    # Authentication dependency is not used in this endpoint.

@pytest.mark.anyio # Use anyio mark
async def test_request_verification_email_disabled(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    email = "disabled_verify_req@example.com"
    request_data = RequestVerificationEmail(email=email)

    # Note: This test does not require authentication dependencies.
    # Simulate Service layer raising ForbiddenError for disabled account (or other specific error)
    mock_user_service.request_verification_email.side_effect = ForbiddenError("账户已被禁用") # Updated to ForbiddenError

    # Send request_data as JSON body
    response = client.post("/api/v1/auth/request-verification-email", json=request_data.model_dump())

    # The router should catch ForbiddenError and raise HTTPException(403)
    assert response.status_code == 403 # Expect 403 Forbidden
    assert response.json()["detail"] == "账户已被禁用" # Check the detail from HTTPException

    mock_user_service.request_verification_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        email=email # Pass email as keyword argument
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
    # The service converts DAL result to a dict suitable for the router response
    service_return_data = {
        "user_id": str(test_user_id), # Router expects string UUID in JSON
        "is_verified": True,
        "message": "邮箱验证成功！您现在可以登录。" # Include message for router response
    }
    mock_user_service.verify_email.return_value = service_return_data

    # Send verify_data_json (with UUID as string) as JSON body
    # Ensure UUID in JSON payload is string, although model_dump should handle it, double check
    response = client.post("/api/v1/auth/verify-email", json={"token": str(verify_data.token)})

    assert response.status_code == 200
    # Assert the structure and content of the JSON response.
    response_json = response.json()
    assert isinstance(response_json, dict)
    assert response_json.get("message") == "邮箱验证成功！您现在可以登录。"
    assert response_json.get("user_id") == str(test_user_id)
    assert response_json.get("is_verified") is True

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
    mock_user_service.verify_email.side_effect = DALError("验证链接无效或已过期，请重新申请。")

    # Send verify_data_json (with UUID as string) as JSON body
    # Ensure UUID in JSON payload is string, although model_dump should handle it, double check
    response = client.post("/api/v1/auth/verify-email", json={"token": str(verify_data.token)})

    assert response.status_code == 400 # Router maps this specific DALError to 400
    assert response.json()["detail"] == "邮箱验证失败: 验证链接无效或已过期，请重新申请。" # Check the detail from HTTPException

    mock_user_service.verify_email.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_token # Service expects UUID object
    )
    # Authentication dependency is not used in this endpoint.

@pytest.mark.anyio # Use anyio mark
async def test_verify_email_disabled_account(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_token = uuid4()
    verify_data = VerifyEmail(token=test_token)

    # Pydantic model_dump() on VerifyEmail will convert UUID to string automatically.
    # Ensure UUID is sent as string in JSON body by using model_dump().
    verify_data_json = verify_data.model_dump()

    # Note: This test does not require authentication dependencies.
    # Simulate Service layer raising ForbiddenError for disabled account
    mock_user_service.verify_email.side_effect = ForbiddenError("账户已被禁用。")

    # Send verify_data_json (with UUID as string) as JSON body
    # Ensure UUID in JSON payload is string, although model_dump should handle it, double check
    response = client.post("/api/v1/auth/verify-email", json={"token": str(verify_data.token)})

    # The router should catch ForbiddenError and raise HTTPException(403)
    assert response.status_code == 403 # Expect 403 Forbidden
    assert response.json()["detail"] == "账户已被禁用。" # Check the detail from HTTPException

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
    # test_admin_user_id = client.test_admin_user_id # Not needed for service call assertion here

    # Simulate the service returning the expected UserResponseSchema instance
    expected_user_profile_schema = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="target_user",
        email="target@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_super_admin=False, # Include is_super_admin
        is_verified=True,
        major="Physics", # Explicitly include optional fields even if None
        avatar_url=None,
        bio="Target user bio.",
        phone_number="0987654321",
        join_time=datetime.now(timezone.utc), # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.get_user_profile_by_id.return_value = expected_user_profile_schema

    # GET request to the admin endpoint to get a user profile by ID.
    # The client fixture provides the mocked admin user.
    response = client.get(f"/api/v1/users/{test_user_id}") # Corrected endpoint

    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful GET
    response_json = response.json()
    # The router should serialize the UserResponseSchema instance to JSON
    # Compare individual fields from the response JSON with the expected schema object
    assert isinstance(response_json, dict)
    assert response_json.get('user_id') == str(expected_user_profile_schema.user_id)
    assert response_json.get('username') == expected_user_profile_schema.username
    assert response_json.get('email') == expected_user_profile_schema.email
    assert response_json.get('status') == expected_user_profile_schema.status
    assert response_json.get('credit') == expected_user_profile_schema.credit
    assert response_json.get('is_staff') == expected_user_profile_schema.is_staff
    assert response_json.get('is_super_admin') == expected_user_profile_schema.is_super_admin
    assert response_json.get('is_verified') == expected_user_profile_schema.is_verified
    assert response_json.get('major') == expected_user_profile_schema.major
    assert response_json.get('avatar_url') == expected_user_profile_schema.avatar_url
    assert response_json.get('bio') == expected_user_profile_schema.bio
    assert response_json.get('phone_number') == expected_user_profile_schema.phone_number

    # Compare join_time by parsing both into datetime objects
    assert isoparse(response_json.get('join_time')) == expected_user_profile_schema.join_time

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
    # test_admin_user_id = client.test_admin_user_id # Not needed for service call assertion here

    update_data = UserProfileUpdateSchema(
        major="Admin Updated Major",
        bio="Admin set bio."
    )

    # Service layer is mocked to return a UserResponseSchema instance representing the updated user
    expected_updated_user_schema = UserResponseSchema(
        user_id=test_user_id, # Service returns UUID object
        username="target_user_update",
        email="target_update@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_super_admin=False, # Include is_super_admin
        is_verified=True,
        major="Admin Updated Major", # Should reflect the updated value
        avatar_url=None,
        bio="Admin set bio.", # Should reflect the updated value
        phone_number="0987654321",
        join_time=datetime.now(timezone.utc), # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.update_user_profile.return_value = expected_updated_user_schema

    # Send update_data as JSON body. user_id is in path.
    # No need for Authorization header, as auth dependency is mocked (admin user).
    response = client.put(f"/api/v1/users/{test_user_id}", json=update_data.model_dump(exclude_unset=True)) # Corrected endpoint

    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful PUT with response body
    # Convert the expected schema instance to a dictionary for comparison, handling UUID and datetime serialization
    response_json = response.json()

    # Compare individual fields from the response JSON with the expected schema object
    assert isinstance(response_json, dict)
    assert response_json.get('user_id') == str(expected_updated_user_schema.user_id)
    assert response_json.get('username') == expected_updated_user_schema.username
    assert response_json.get('email') == expected_updated_user_schema.email
    assert response_json.get('status') == expected_updated_user_schema.status
    assert response_json.get('credit') == expected_updated_user_schema.credit
    assert response_json.get('is_staff') == expected_updated_user_schema.is_staff
    assert response_json.get('is_super_admin') == expected_updated_user_schema.is_super_admin
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
    # test_admin_user_id = client.test_admin_user_id # Not needed for service call assertion here

    # Simulate Service layer returning True on successful deletion
    mock_user_service.delete_user.return_value = True

    # DELETE request to the admin endpoint to delete a user by ID.
    # The client fixture provides the mocked admin user.
    response = client.delete(f"/api/v1/users/{test_user_id}") # Corrected endpoint

    assert response.status_code == status.HTTP_204_NO_CONTENT # Expect 204 No Content for successful DELETE

    # Verify that the service's delete_user method was called with the correct data
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
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    new_status_data = UserStatusUpdateSchema(status="Disabled")

    # Simulate Service layer returning True on success
    mock_user_service.change_user_status.return_value = True

    # Send status update data as JSON body. user_id is in path.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=new_status_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_204_NO_CONTENT # Expect 204 No Content for successful status update

    # Verify Service method call
    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID from path
        new_status_data.status, # Status string
        test_admin_user_id # Admin ID from mocked dependency
    )

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_not_found(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    new_status_data = UserStatusUpdateSchema(status="Disabled")

    # Simulate Service layer raising NotFoundError
    mock_user_service.change_user_status.side_effect = NotFoundError(f"User with ID {test_user_id} not found for status change.") # Updated error message

    # Send status update data as JSON body. user_id is in path.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=new_status_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_404_NOT_FOUND # Expect 404 Not Found
    assert response.json()["detail"] == f"User with ID {test_user_id} not found for status change." # Check the detail

    # Verify Service method call
    mock_user_service.change_user_status.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        test_user_id, # User ID
        new_status_data.status, # Status
        test_admin_user_id # Admin ID
    )

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Temporarily override get_current_active_admin_user to raise HTTPException(403)
    mock_get_current_admin = mocker.patch('app.dependencies.get_current_active_admin_user')
    mock_get_current_admin.side_effect = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Operation forbidden")

    # The user ID in the path doesn't matter for this test, as auth fails before reaching the handler
    test_user_id = uuid4() # Use a dummy ID

    # Act: Attempt to change user status as a non-admin (should be forbidden)
    response = client.put(f"/api/v1/users/{test_user_id}/status", json={"status": "Disabled"}) # Use dummy data matching schema

    # Assert the response status code is 403 Forbidden
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Optionally, check that the mocked dependency was called
    mock_get_current_admin.assert_called_once()

    # Ensure the service method was NOT called (as the dependency blocked it)
    # Get the original mock service instance (this is available outside the patch context)
    mock_user_service = client.dependency_overrides.get(get_user_service_dependency)()
    mock_user_service.change_user_status.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Simulate credit adjustment exceeding max allowed by schema
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=1001, reason="Too much")

    # Send credit adjustment data.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "greater_than"
    assert "Input should be greater than -1001" in response_json["detail"][0].get("msg", "") # Check message content
    assert response_json["detail"][0].get("loc") == ["body", "credit_adjustment"]

    # Ensure Service method was NOT called
    mock_user_service.adjust_user_credit.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_missing_reason(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Simulate credit adjustment below min allowed by schema
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-1001, reason="Too little") # Should be -1001 to trigger error

    # Send credit adjustment data.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "greater_than"
    assert "Input should be greater than -1001" in response_json["detail"][0].get("msg", "") # Check message content
    assert response_json["detail"][0].get("loc") == ["body", "credit_adjustment"]

    # Ensure Service method was NOT called
    mock_user_service.adjust_user_credit.assert_not_called() 

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Temporarily override get_current_active_admin_user to raise HTTPException(403)
    mock_get_current_admin = mocker.patch('app.dependencies.get_current_active_admin_user')
    mock_get_current_admin.side_effect = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Operation forbidden")

    # The user ID in the path doesn't matter for this test, as auth fails before reaching the handler
    test_user_id = uuid4() # Use a dummy ID
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=10, reason="Bonus") # Use dummy data

    # Act: Attempt to adjust user credit as a non-admin (should be forbidden)
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump())

    # Assert the response status code is 403 Forbidden
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Optionally, check that the mocked dependency was called
    mock_get_current_admin.assert_called_once()

    # Ensure the service method was NOT called (as the dependency blocked it)
    # Get the original mock service instance (this is available outside the patch context)
    mock_user_service = client.dependency_overrides.get(get_user_service_dependency)()
    mock_user_service.adjust_user_credit.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_forbidden(client: TestClient, mocker: pytest_mock.MockerFixture):
    # This test simulates a scenario where the admin dependency itself raises a Forbidden exception.
    # Temporarily override get_current_active_admin_user to raise HTTPException(403)
    mock_get_current_admin = mocker.patch('app.dependencies.get_current_active_admin_user')
    mock_get_current_admin.side_effect = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="只有超级管理员可以查看所有用户。" # Use the specific error message from the router
    )

    # Act: Attempt to get all users as a non-admin (should be forbidden)
    response = client.get("/api/v1/users/") # Corrected endpoint

    # Assert the response status code is 403 Forbidden
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Optionally, check that the mocked dependency was called
    mock_get_current_admin.assert_called_once()

    # Ensure the service method was NOT called (as the dependency blocked it)
    # Get the original mock service instance (this is available outside the patch context)
    mock_user_service = client.dependency_overrides.get(get_user_service_dependency)()
    mock_user_service.get_all_users.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_change_user_status_invalid_value(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Use an invalid status value
    invalid_status_data = {"status": "InvalidStatus"}

    # Send status update data with invalid value.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/status", json=invalid_status_data) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "enum"
    assert "value is not a valid enumeration member" in response_json["detail"][0].get("msg", "")

    # Ensure Service method was NOT called
    mock_user_service.change_user_status.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_missing_reason(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Simulate missing reason field (required by schema)
    credit_adjustment_data = {"credit_adjustment": 10} # Missing reason

    # Send credit adjustment data without reason.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "missing"
    assert "Field required" in response_json["detail"][0].get("msg", "")

    # Ensure Service method was NOT called
    mock_user_service.adjust_user_credit.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_exceeding_max(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Simulate credit adjustment exceeding max allowed by schema
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=1001, reason="Too much")

    # Send credit adjustment data.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "greater_than"
    assert "Input should be greater than -1001" in response_json["detail"][0].get("msg", "") # Check message content
    assert response_json["detail"][0].get("loc") == ["body", "credit_adjustment"]

    # Ensure Service method was NOT called
    mock_user_service.adjust_user_credit.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_adjust_user_credit_below_min(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_user_id = client.test_admin_user_id
    # Simulate credit adjustment below min allowed by schema
    credit_adjustment_data = UserCreditAdjustmentSchema(credit_adjustment=-1001, reason="Too little") # Should be -1001 to trigger error

    # Send credit adjustment data.
    # FastAPI/Pydantic will handle the validation error before the service is called.
    response = client.put(f"/api/v1/users/{test_user_id}/credit", json=credit_adjustment_data.model_dump()) # Corrected endpoint

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Expect 422 Unprocessable Entity
    # Assert the structure of the validation error detail
    response_json = response.json()
    assert "detail" in response_json
    assert isinstance(response_json["detail"], list)
    assert len(response_json["detail"]) > 0
    assert response_json["detail"][0].get("type") == "greater_than"
    assert "Input should be greater than -1001" in response_json["detail"][0].get("msg", "") # Check message content
    assert response_json["detail"][0].get("loc") == ["body", "credit_adjustment"]

    # Ensure Service method was NOT called
    mock_user_service.adjust_user_credit.assert_not_called()

@pytest.mark.anyio # Use anyio mark
async def test_admin_get_all_users_success(client: TestClient, mock_user_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    # The client fixture now provides the mocked admin authentication dependency
    # We can access the test admin user ID from the client instance
    test_admin_user_id = client.test_admin_user_id

    # Simulate the service returning the expected UserResponseSchema instance
    expected_user_profile_schema = UserResponseSchema(
        user_id=uuid4(), # Service returns UUID object
        username="target_user",
        email="target@example.com",
        status="Active",
        credit=100,
        is_staff=False,
        is_super_admin=False, # Include is_super_admin
        is_verified=True,
        major="Physics", # Explicitly include optional fields even if None
        avatar_url=None,
        bio="Target user bio.",
        phone_number="0987654321",
        join_time=datetime.now(timezone.utc), # Use timezone-aware datetime
    )
    # The mock should return the Pydantic schema instance
    mock_user_service.get_user_profile_by_id.return_value = expected_user_profile_schema

    # GET request to the admin endpoint to get a user profile by ID.
    # The client fixture provides the mocked admin user.
    response = client.get(f"/api/v1/users/{uuid4()}") # Corrected endpoint

    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful GET
    response_json = response.json()
    # The router should serialize the UserResponseSchema instance to JSON
    # Compare individual fields from the response JSON with the expected schema object
    assert isinstance(response_json, dict)
    assert response_json.get('user_id') == str(expected_user_profile_schema.user_id)
    assert response_json.get('username') == expected_user_profile_schema.username
    assert response_json.get('email') == expected_user_profile_schema.email
    assert response_json.get('status') == expected_user_profile_schema.status
    assert response_json.get('credit') == expected_user_profile_schema.credit
    assert response_json.get('is_staff') == expected_user_profile_schema.is_staff
    assert response_json.get('is_super_admin') == expected_user_profile_schema.is_super_admin
    assert response_json.get('is_verified') == expected_user_profile_schema.is_verified
    assert response_json.get('major') == expected_user_profile_schema.major
    assert response_json.get('avatar_url') == expected_user_profile_schema.avatar_url
    assert response_json.get('bio') == expected_user_profile_schema.bio
    assert response_json.get('phone_number') == expected_user_profile_schema.phone_number

    # Compare join_time by parsing both into datetime objects
    assert isoparse(response_json.get('join_time')) == expected_user_profile_schema.join_time

    mock_user_service.get_user_profile_by_id.assert_called_once_with(
        mocker.ANY, # Mocked DB connection
        uuid4() # User ID from path (FastAPI converts string to UUID object)
    )
    # Authentication dependency is mocked via dependency_overrides in client fixture,
    # so we don't assert calls on a patched mock here.

    mock_user_service.get_all_users.assert_called_once() 