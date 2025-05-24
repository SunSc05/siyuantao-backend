import pytest
import pytest_mock
from httpx import AsyncClient

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from app.services.user_service import UserService
from app.dal.user_dal import UserDAL
from app.schemas.user_schemas import UserRegisterSchema, UserLoginSchema, UserPasswordUpdate, UserProfileUpdateSchema, UserStatusUpdateSchema, UserCreditAdjustmentSchema, UserResponseSchema # Import necessary schemas
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions
from datetime import datetime

# Mock Fixture for UserDAL
@pytest.fixture
def mock_user_dal(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Mock the UserDAL dependency."""
    # Create an AsyncMock instance for the UserDAL class methods
    return AsyncMock(spec=UserDAL)

# Fixture for UserService with Mocked DAL
@pytest.fixture
def user_service(mock_user_dal: AsyncMock) -> UserService:
    """Provides a UserService instance with a mocked UserDAL."""
    return UserService(user_dal=mock_user_dal)

# Mock Fixture for Database Connection
@pytest.fixture
def mock_db_connection(mocker: pytest_mock.MockerFixture) -> MagicMock:
    """Mock a database connection object."""
    # Use MagicMock for connection as it might have various attributes/methods used by DAL
    return MagicMock()

# Mock Fixture for app.utils.auth
@pytest.fixture
def mock_utils_auth(mocker: pytest_mock.MockerFixture):
    """Mock the utility functions in app.utils.auth."""
    mock_get_password_hash = mocker.patch('app.services.user_service.get_password_hash', return_value="hashed_password") # Patch where it's used in Service
    mock_verify_password = mocker.patch('app.services.user_service.verify_password', return_value=True) # Patch where it's used in Service
    mock_create_access_token = mocker.patch('app.services.user_service.create_access_token', return_value="mock_jwt_token") # Patch where it's used in Service
    return mock_get_password_hash, mock_verify_password, mock_create_access_token # Return mocks if needed for assertions

# --- UserService Unit Tests --- 

@pytest.mark.asyncio
async def test_create_user_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    username = "testuser_service"
    email = "test_service@example.com"
    password = "securepassword"
    user_data = UserRegisterSchema(username=username, email=email, password=password)
    
    test_user_id = uuid4() # Simulate a generated UUID
    # Simulate DAL returning user data with DB-like keys (PascalCase or Chinese)
    # Ensure all expected keys by _convert_dal_user_to_schema are present, including optional ones with None values
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": username,
        "邮箱": email,
        "Status": "Active",
        "Credit": 100,
        "IsStaff": False,
        "IsVerified": False,
        "Major": user_data.major, # Ensure optional fields from input are present if provided
        "AvatarUrl": None,
        "Bio": None,
        "PhoneNumber": None,
        "JoinTime": datetime(2023, 1, 1, 12, 0, 0) # Simulate datetime object
    }
    
    # Mock the DAL method to return the simulated data
    mock_user_dal.create_user.return_value = dal_return_data # DAL returns the created user data
    
    # Call the service function
    created_user = await user_service.create_user(mock_db_connection, user_data)
    
    # Assertions on the service function's return value
    # Service should return a UserResponseSchema instance
    assert isinstance(created_user, UserResponseSchema)
    # Assert the attributes of the Pydantic model instance
    assert created_user.user_id == test_user_id # Service returns UUID object now
    assert created_user.username == username
    assert created_user.email == email
    assert created_user.status == "Active"
    assert created_user.credit == 100
    assert created_user.is_staff is False
    assert created_user.is_verified is False
    assert created_user.major == user_data.major
    assert created_user.avatar_url is None
    assert created_user.bio is None
    assert created_user.phone_number is None
    # Service returns datetime object now, compare as such or check type
    assert isinstance(created_user.join_time, datetime) # Check type
    assert created_user.join_time == datetime(2023, 1, 1, 12, 0, 0) # Compare with datetime object

    # Verify that the DAL method was called with correct arguments
    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection, # Connection is passed through
        username,
        email,
        "hashed_password" # Verify hashed password is passed
        # Ensure optional fields are passed if DAL supports them and they were provided in input data
    )
    
    # Verify password hashing utility was called
    mock_utils_auth[0].assert_called_once_with(password) # get_password_hash called with raw password

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    user_data = UserRegisterSchema(username="dup_user", email="dup@example.com", password="password")

    # Simulate DAL raising IntegrityError for duplicate username
    mock_user_dal.create_user.side_effect = IntegrityError("Username already exists.")

    with pytest.raises(IntegrityError, match="Username already exists."):
        await user_service.create_user(mock_db_connection, user_data)

    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection,
        user_data.username,
        user_data.email,
        "hashed_password"
    )
    mock_utils_auth[0].assert_called_once_with(user_data.password)

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    user_data = UserRegisterSchema(username="user3", email="dup@example.com", password="password")

    # Simulate DAL raising IntegrityError for duplicate email
    mock_user_dal.create_user.side_effect = IntegrityError("Email already exists.")

    with pytest.raises(IntegrityError, match="Email already exists."):
        await user_service.create_user(mock_db_connection, user_data)

    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection,
        user_data.username,
        user_data.email,
        "hashed_password"
    )
    mock_utils_auth[0].assert_called_once_with(user_data.password)

@pytest.mark.asyncio
async def test_create_user_dal_error(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    user_data = UserRegisterSchema(username="error_user", email="error@example.com", password="password")

    # Simulate DAL raising a generic DALError
    mock_user_dal.create_user.side_effect = DALError("Database connection failed.")

    with pytest.raises(DALError, match="Database connection failed."):
        await user_service.create_user(mock_db_connection, user_data)

    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection,
        user_data.username,
        user_data.email,
        "hashed_password"
    )
    mock_utils_auth[0].assert_called_once_with(user_data.password)

@pytest.mark.asyncio
async def test_get_user_profile_by_id_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    # Simulate DAL returning user data with DB-like keys (PascalCase or Chinese)
    # Ensure all expected keys by _convert_dal_user_to_schema are present, including optional ones with None values
    dal_return_data = {
        "用户ID": test_user_id, # Example with Chinese key
        "用户名": "test_user",
        "邮箱": "test@example.com",
        "账户状态": "Active",
        "信用分": 95,
        "是否管理员": False,
        "是否已认证": True,
        "专业": "CS",
        "头像URL": None,
        "个人简介": "Some bio",
        "手机号码": "1234567890",
        "注册时间": datetime(2023, 1, 5, 10, 30, 0)
    }
    mock_user_dal.get_user_by_id.return_value = dal_return_data

    # Call the service function
    user_profile = await user_service.get_user_profile_by_id(mock_db_connection, test_user_id)

    # Assertions on the service function's return value
    # Service should return a UserResponseSchema instance
    assert isinstance(user_profile, UserResponseSchema)
    # Assert the attributes of the Pydantic model instance
    assert user_profile.user_id == test_user_id # Service returns UUID object
    assert user_profile.username == "test_user"
    assert user_profile.email == "test@example.com"
    assert user_profile.status == "Active"
    assert user_profile.credit == 95
    assert user_profile.is_staff is False
    assert user_profile.is_verified is True
    assert user_profile.major == "CS"
    assert user_profile.avatar_url is None
    assert user_profile.bio == "Some bio"
    assert user_profile.phone_number == "1234567890"
    # Service returns datetime object, compare as such or check type
    assert isinstance(user_profile.join_time, datetime) # Check type
    assert user_profile.join_time == datetime(2023, 1, 5, 10, 30, 0) # Compare with datetime object

    # Verify DAL method was called with correct arguments
    mock_user_dal.get_user_by_id.assert_called_once_with(
        mock_db_connection,
        test_user_id
    )

@pytest.mark.asyncio
async def test_get_user_profile_by_id_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    # Simulate DAL returning None
    mock_user_dal.get_user_by_id.return_value = None

    # Call the service function and assert it raises NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found."):
        await user_service.get_user_profile_by_id(mock_db_connection, test_user_id)

    # Verify DAL method was called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    username = "loginuser"
    password = "correctpassword"
    test_user_id = uuid4()
    
    # Simulate DAL returning user data with password hash
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": username,
        "Password": "hashed_password", # Must match the return value of mock_utils_auth[0]
        "Status": "Active",
        "IsStaff": False,
        "IsVerified": True,
        # Include other fields expected by token creation or later steps if necessary
    }
    mock_user_dal.get_user_by_username_with_password.return_value = dal_return_data

    # Configure mock_utils_auth[1] (verify_password) to return True
    mock_utils_auth[1].return_value = True

    # Call the service function
    token = await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Assertions
    assert isinstance(token, str)
    assert token == "mock_jwt_token" # Should match the return value of mock_utils_auth[2]

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)
    # Verify password verification utility was called
    mock_utils_auth[1].assert_called_once_with(password, "hashed_password")
    # Verify token creation utility was called
    # Check the data passed to create_access_token
    mock_utils_auth[2].assert_called_once()
    # Check the first argument (data payload) of the create_access_token call
    called_args, called_kwargs = mock_utils_auth[2].call_args
    token_payload = called_kwargs.get('data') or called_args[0]
    assert token_payload["user_id"] == str(test_user_id)
    assert token_payload["is_staff"] is False
    assert token_payload["is_verified"] is True
    # Check the second argument (expires_delta)
    assert "expires_delta" in called_kwargs or len(called_args) > 1 # Ensure expires_delta is passed

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_invalid_password(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    username = "loginuser"
    password = "wrongpassword"
    test_user_id = uuid4()

    # Simulate DAL returning user data with password hash
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": username,
        "Password": "hashed_password",
        "Status": "Active",
        "IsStaff": False,
        "IsVerified": True,
    }
    mock_user_dal.get_user_by_username_with_password.return_value = dal_return_data

    # Configure mock_utils_auth[1] (verify_password) to return False
    mock_utils_auth[1].return_value = False

    # Call the service function and assert it raises AuthenticationError
    with pytest.raises(AuthenticationError, match="用户名或密码不正确"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)
    # Verify password verification utility was called
    mock_utils_auth[1].assert_called_once_with(password, "hashed_password")
    # Verify token creation utility was NOT called
    mock_utils_auth[2].assert_not_called()

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    username = "nonexistentuser"
    password = "anypassword"

    # Simulate DAL returning None (user not found)
    mock_user_dal.get_user_by_username_with_password.return_value = None

    # Call the service function and assert it raises AuthenticationError
    with pytest.raises(AuthenticationError, match="用户名或密码不正确"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)
    # Verify password verification utility was NOT called
    mock_utils_auth[1].assert_not_called()
    # Verify token creation utility was NOT called
    mock_utils_auth[2].assert_not_called()

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    username = "disableduser"
    password = "correctpassword"
    test_user_id = uuid4()

    # Simulate DAL returning user data with status Disabled
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": username,
        "Password": "hashed_password",
        "Status": "Disabled", # User is disabled
        "IsStaff": False,
        "IsVerified": True,
    }
    mock_user_dal.get_user_by_username_with_password.return_value = dal_return_data

    # Configure mock_utils_auth[1] (verify_password) to return True
    mock_utils_auth[1].return_value = True

    # Call the service function and assert it raises ForbiddenError
    with pytest.raises(ForbiddenError, match="账户已被禁用"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)
    # Verify password verification utility was called
    mock_utils_auth[1].assert_called_once_with(password, "hashed_password")
    # Verify token creation utility was NOT called
    mock_utils_auth[2].assert_not_called()

@pytest.mark.asyncio
async def test_update_user_profile_success_with_updates(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(
        major="New Major",
        bio="Updated bio."
        # phone_number=None # Explicitly setting optional fields
    )

    # Simulate DAL returning the updated user data
    # Ensure all expected keys by _convert_dal_user_to_schema are present, including optional ones with None values
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": "original_user",
        "邮箱": "original@example.com",
        "Status": "Active",
        "Credit": 100,
        "IsStaff": False,
        "IsVerified": True,
        "Major": update_data.major if update_data.major is not None else "Original Major", # Reflect update or original value
        "AvatarUrl": update_data.avatar_url if update_data.avatar_url is not None else "original_avatar.jpg",
        "Bio": update_data.bio if update_data.bio is not None else "Original bio.",
        "PhoneNumber": update_data.phone_number if update_data.phone_number is not None else "1234567890",
        "JoinTime": datetime(2023, 1, 1, 12, 0, 0)
    }
    mock_user_dal.update_user_profile.return_value = dal_return_data

    # Call the service function
    updated_user = await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)

    # Assertions on the service function's return value
    # Service should return a UserResponseSchema instance
    assert isinstance(updated_user, UserResponseSchema)
    assert updated_user.user_id == test_user_id # Service returns UUID object
    assert updated_user.major == "New Major"
    assert updated_user.bio == "Updated bio."
    # Assert other fields remain as in the simulated DAL return
    assert updated_user.username == "original_user"
    assert updated_user.email == "original@example.com"
    assert updated_user.status == "Active"
    assert updated_user.credit == 100
    assert updated_user.is_staff is False
    assert updated_user.is_verified is True
    assert updated_user.avatar_url == "original_avatar.jpg"
    assert updated_user.phone_number == "1234567890"
    assert isinstance(updated_user.join_time, datetime) # Ensure it's a datetime object
    assert updated_user.join_time == dal_return_data["JoinTime"] # Compare with datetime object

    # Verify DAL method was called with correct arguments
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major="New Major",
        avatar_url=mocker.ANY, # avatar_url was not set in update_data, should be None or DAL default
        bio="Updated bio.",
        phone_number=mocker.ANY # phone_number was not set in update_data, should be None or DAL default
    )

@pytest.mark.asyncio
async def test_update_user_profile_success_no_updates(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    # Create an empty update data schema (no fields set)
    update_data = UserProfileUpdateSchema()

    # Simulate DAL returning the current user profile (since no updates are made)
    # Ensure all expected keys by _convert_dal_user_to_schema are present, including optional ones with None values
    dal_return_data = {
        "UserID": test_user_id,
        "UserName": "current_user",
        "邮箱": "current@example.com",
        "Status": "Active",
        "Credit": 100,
        "IsStaff": False,
        "IsVerified": True,
        "Major": "Original Major",
        "AvatarUrl": "original_avatar.jpg",
        "Bio": "Original bio.",
        "PhoneNumber": "1234567890",
        "JoinTime": datetime(2023, 1, 1, 12, 0, 0)
    }
    # When no update data is provided, service calls get_user_profile_by_id
    mock_user_dal.get_user_by_id.return_value = dal_return_data
    # update_user_profile should not be called in this case
    mock_user_dal.update_user_profile.assert_not_called()

    # Call the service function
    updated_user = await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)

    # Assertions on the service function's return value
    # Service should return a UserResponseSchema instance
    assert isinstance(updated_user, UserResponseSchema)
    assert updated_user.user_id == test_user_id # Service returns UUID object
    assert updated_user.major == "Original Major"
    assert updated_user.bio == "Original bio."
    # Assert other fields remain as in the simulated DAL return
    assert updated_user.username == "current_user"
    assert updated_user.email == "current@example.com"
    assert updated_user.status == "Active"
    assert updated_user.credit == 100
    assert updated_user.is_staff is False
    assert updated_user.is_verified is True
    assert updated_user.avatar_url == "original_avatar.jpg"
    assert updated_user.phone_number == "1234567890"
    assert isinstance(updated_user.join_time, datetime) # Ensure it's a datetime object
    assert updated_user.join_time == dal_return_data["JoinTime"] # Compare with datetime object

    # Verify get_user_by_id was called to fetch current profile
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    # Verify update_user_profile was NOT called
    mock_user_dal.update_user_profile.assert_not_called()

@pytest.mark.asyncio
async def test_update_user_profile_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(major="New Major")

    # Simulate DAL raising NotFoundError
    mock_user_dal.update_user_profile.side_effect = NotFoundError(f"User with ID {test_user_id} not found for update.")

    # Call the service function and assert it raises NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found for update."):
        await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)

    # Verify DAL method was called
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major="New Major",
        avatar_url=mocker.ANY,
        bio=mocker.ANY,
        phone_number=mocker.ANY
    )

@pytest.mark.asyncio
async def test_update_user_profile_duplicate_phone(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(phone_number="999888777")

    # Simulate DAL raising IntegrityError
    mock_user_dal.update_user_profile.side_effect = IntegrityError("Phone number already in use by another user.")

    # Call the service function and assert it raises IntegrityError
    with pytest.raises(IntegrityError, match="Phone number already in use by another user."):
        await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)

    # Verify DAL method was called
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major=mocker.ANY,
        avatar_url=mocker.ANY,
        bio=mocker.ANY,
        phone_number="999888777"
    )

@pytest.mark.asyncio
async def test_update_user_password_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    password_update_data = UserPasswordUpdate(old_password="oldpassword", new_password="newpassword")

    # Simulate DAL returning user data including username for the first call (get_user_by_id)
    mock_user_dal.get_user_by_id.return_value = {"UserID": test_user_id, "用户名": "testuser_pass"} # Need username

    # Simulate DAL returning user data including password hash for the second call (get_user_by_username_with_password)
    mock_user_dal.get_user_by_username_with_password.return_value = {
        "UserID": test_user_id,
        "UserName": "testuser_pass",
        "Password": "hashed_old_password"
        # Include other minimal required fields
    }

    # Configure mock_utils_auth[1] (verify_password) to return True for the old password
    mock_utils_auth[1].return_value = True

    # Simulate DAL.update_user_password returning True on success
    mock_user_dal.update_user_password.return_value = True

    # Configure mock_utils_auth[0] (get_password_hash) to return hashed new password
    mock_utils_auth[0].return_value = "hashed_new_password"

    # Call the service function
    update_success = await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Assertions
    assert update_success is True

    # Verify DAL methods were called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, "testuser_pass")
    mock_user_dal.update_user_password.assert_called_once_with(mock_db_connection, test_user_id, "hashed_new_password")

    # Verify auth utilities were called
    mock_utils_auth[1].assert_called_once_with("oldpassword", "hashed_old_password") # verify_password called
    mock_utils_auth[0].assert_called_once_with("newpassword") # get_password_hash called

@pytest.mark.asyncio
async def test_update_user_password_wrong_old_password(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    password_update_data = UserPasswordUpdate(old_password="wrongpassword", new_password="newpassword")

    # Simulate DAL returning user data including username and password hash
    mock_user_dal.get_user_by_id.return_value = {"UserID": test_user_id, "用户名": "testuser_pass"}
    mock_user_dal.get_user_by_username_with_password.return_value = {
        "UserID": test_user_id,
        "UserName": "testuser_pass",
        "Password": "hashed_old_password"
    }

    # Configure mock_utils_auth[1] (verify_password) to return False
    mock_utils_auth[1].return_value = False

    # Call the service function and assert it raises AuthenticationError
    with pytest.raises(AuthenticationError, match="旧密码不正确"):
        await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Verify DAL methods were called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, "testuser_pass")
    mock_user_dal.update_user_password.assert_not_called() # Update should not happen

    # Verify auth utilities were called
    mock_utils_auth[1].assert_called_once_with("wrongpassword", "hashed_old_password")
    mock_utils_auth[0].assert_not_called() # Hashing new password should not happen

@pytest.mark.asyncio
async def test_update_user_password_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    password_update_data = UserPasswordUpdate(old_password="oldpassword", new_password="newpassword")

    # Simulate DAL.get_user_by_id raising NotFoundError
    mock_user_dal.get_user_by_id.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")

    # Call the service function and assert it raises NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found."):
        await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Verify DAL method was called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    mock_user_dal.get_user_by_username_with_password.assert_not_called()
    mock_user_dal.update_user_password.assert_not_called()
    mock_utils_auth[0].assert_not_called()
    mock_utils_auth[1].assert_not_called()

@pytest.mark.asyncio
async def test_delete_user_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()

    # Simulate DAL returning True on successful deletion
    mock_user_dal.delete_user.return_value = True

    # Call the service function
    delete_success = await user_service.delete_user(mock_db_connection, test_user_id)

    # Assertions
    assert delete_success is True

    # Verify DAL method was called
    mock_user_dal.delete_user.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_delete_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()

    # Simulate DAL raising NotFoundError
    mock_user_dal.delete_user.side_effect = NotFoundError(f"User with ID {test_user_id} not found for deletion.")

    # Call the service function and assert it raises NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found for deletion."):
        await user_service.delete_user(mock_db_connection, test_user_id)

    # Verify DAL method was called
    mock_user_dal.delete_user.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_request_verification_email_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    email = "verify_req@example.com"
    test_user_id = uuid4()
    test_token = uuid4()

    # Simulate DAL returning success result
    dal_return_data = {
        "VerificationToken": test_token,
        "UserID": test_user_id,
        "IsNewUser": True
    }
    mock_user_dal.request_verification_link.return_value = dal_return_data

    # Call the service function
    link_result = await user_service.request_verification_email(mock_db_connection, email)

    # Assertions
    assert isinstance(link_result, dict)
    assert link_result["VerificationToken"] == test_token
    assert link_result["UserID"] == test_user_id
    assert link_result["IsNewUser"] is True

    # Verify DAL method was called
    mock_user_dal.request_verification_link.assert_called_once_with(mock_db_connection, email)

@pytest.mark.asyncio
async def test_request_verification_email_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    email = "disabled_req@example.com"

    # Simulate DAL raising DALError for disabled account
    mock_user_dal.request_verification_link.side_effect = DALError("Account is disabled.")

    # Call the service function and assert it raises DALError
    with pytest.raises(DALError, match="Account is disabled."):
        await user_service.request_verification_email(mock_db_connection, email)

    # Verify DAL method was called
    mock_user_dal.request_verification_link.assert_called_once_with(mock_db_connection, email)

@pytest.mark.asyncio
async def test_verify_email_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_token = uuid4()
    test_user_id = uuid4()

    # Simulate DAL returning success result
    dal_return_data = {
        "UserID": test_user_id,
        "IsVerified": True
    }
    mock_user_dal.verify_email.return_value = dal_return_data

    # Call the service function
    verification_result = await user_service.verify_email(mock_db_connection, test_token)

    # Assertions
    assert isinstance(verification_result, dict)
    assert verification_result["UserID"] == test_user_id
    assert verification_result["IsVerified"] is True

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)

@pytest.mark.asyncio
async def test_verify_email_invalid_or_expired_token(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_token = uuid4()

    # Simulate DAL raising DALError for invalid/expired token
    mock_user_dal.verify_email.side_effect = DALError("Magic link invalid or expired.")

    # Call the service function and assert it raises DALError
    with pytest.raises(DALError, match="Magic link invalid or expired."):
        await user_service.verify_email(mock_db_connection, test_token)

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)

@pytest.mark.asyncio
async def test_verify_email_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_token = uuid4()

    # Simulate DAL raising DALError for disabled account
    mock_user_dal.verify_email.side_effect = DALError("Account is disabled.")

    # Call the service function and assert it raises DALError
    with pytest.raises(DALError, match="Account is disabled."):
        await user_service.verify_email(mock_db_connection, test_token)

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)

@pytest.mark.asyncio
async def test_get_system_notifications_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    # Simulate DAL returning a list of notification dicts
    dal_return_data = [
        {"NotificationID": uuid4(), "UserID": test_user_id, "Message": "Notification 1", "IsRead": False, "CreatedAt": datetime.now()},
        {"NotificationID": uuid4(), "UserID": test_user_id, "Message": "Notification 2", "IsRead": True, "CreatedAt": datetime.now()},
    ]
    mock_user_dal.get_system_notifications_by_user_id.return_value = dal_return_data

    # Call the service function
    notifications = await user_service.get_system_notifications(mock_db_connection, test_user_id)

    # Assertions (Service layer doesn't convert keys for notifications currently)
    assert isinstance(notifications, list)
    assert len(notifications) == 2
    assert notifications[0]["Message"] == "Notification 1"
    assert notifications[1]["IsRead"] is True

    # Verify DAL method was called
    mock_user_dal.get_system_notifications_by_user_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_get_system_notifications_no_notifications(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    # Simulate DAL returning an empty list
    mock_user_dal.get_system_notifications_by_user_id.return_value = []

    # Call the service function
    notifications = await user_service.get_system_notifications(mock_db_connection, test_user_id)

    # Assertions
    assert isinstance(notifications, list)
    assert len(notifications) == 0

    # Verify DAL method was called
    mock_user_dal.get_system_notifications_by_user_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_mark_system_notification_as_read_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL returning True on success
    mock_user_dal.mark_notification_as_read.return_value = True

    # Call the service function
    success = await user_service.mark_system_notification_as_read(mock_db_connection, test_notification_id, test_user_id)

    # Assertions
    assert success is True

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, test_notification_id, test_user_id)

@pytest.mark.asyncio
async def test_mark_system_notification_as_read_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL raising NotFoundError
    mock_user_dal.mark_notification_as_read.side_effect = NotFoundError(f"Notification with ID {test_notification_id} not found.")

    # Call the service function and assert it raises NotFoundError
    with pytest.raises(NotFoundError, match=f"Notification with ID {test_notification_id} not found."):
        await user_service.mark_system_notification_as_read(mock_db_connection, test_notification_id, test_user_id)

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, test_notification_id, test_user_id)

@pytest.mark.asyncio
async def test_mark_system_notification_as_read_forbidden(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL raising ForbiddenError
    mock_user_dal.mark_notification_as_read.side_effect = ForbiddenError(f"User {test_user_id} does not have permission.")

    # Call the service function and assert it raises ForbiddenError
    with pytest.raises(ForbiddenError, match=f"User {test_user_id} does not have permission."):
        await user_service.mark_system_notification_as_read(mock_db_connection, test_notification_id, test_user_id)

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, test_notification_id, test_user_id)


# New tests for admin methods

@pytest.mark.asyncio
async def test_change_user_status_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_id = uuid4()
    new_status = "Disabled"

    # Simulate DAL returning True on success
    mock_user_dal.change_user_status.return_value = True

    # Call the service function with all required arguments
    success = await user_service.change_user_status(mock_db_connection, test_user_id, new_status, test_admin_id) # <-- Pass admin_id

    # Assertions
    assert success is True

    # Verify DAL method was called with correct arguments
    mock_user_dal.change_user_status.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        new_status,
        test_admin_id # Verify admin_id is passed
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_user_id = uuid4()
    test_admin_id = uuid4()
    credit_adjustment = 50
    reason = "Bonus"

    # Simulate DAL returning True on success
    mock_user_dal.adjust_user_credit.return_value = True

    # Call the service function with all required arguments
    success = await user_service.adjust_user_credit(mock_db_connection, test_user_id, credit_adjustment, test_admin_id, reason) # <-- Pass admin_id and reason

    # Assertions
    assert success is True

    # Verify DAL method was called with correct arguments
    mock_user_dal.adjust_user_credit.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        credit_adjustment,
        test_admin_id, # Verify admin_id is passed
        reason # Verify reason is passed
    )

@pytest.mark.asyncio
async def test_get_all_users_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_admin_id = uuid4()

    # Simulate DAL returning a list of user dictionaries with DB-like keys
    # Ensure all expected keys by _convert_dal_user_to_schema are present in each dict
    dal_return_data = [
        {
            "UserID": uuid4(),
            "UserName": "user1",
            "邮箱": "user1@example.com",
            "Status": "Active",
            "Credit": 100,
            "IsStaff": False,
            "IsVerified": True,
            "Major": "CS",
            "AvatarUrl": "url1", # Added non-None avatar_url for testing
            "Bio": "User 1 bio.",
            "PhoneNumber": "1111111111",
            "JoinTime": datetime(2023, 1, 1, 12, 0, 0)
        },
        {
            "UserID": uuid4(),
            "UserName": "user2",
            "邮箱": "user2@example.com",
            "Status": "Disabled",
            "Credit": 50,
            "IsStaff": False,
            "IsVerified": False,
            "Major": None,
            "AvatarUrl": None,
            "Bio": None,
            "PhoneNumber": None,
            "JoinTime": datetime(2023, 1, 2, 12, 0, 0)
        }
    ]
    mock_user_dal.get_all_users.return_value = dal_return_data

    # Call the service function
    users_list = await user_service.get_all_users(mock_db_connection, test_admin_id)

    # Assertions on the service function's return value
    # Service should return a list of UserResponseSchema instances
    assert isinstance(users_list, list)
    assert len(users_list) == 2
    assert isinstance(users_list[0], UserResponseSchema)
    assert isinstance(users_list[1], UserResponseSchema)
    # Assert attributes of the first user (Pydantic model instance)
    assert users_list[0].user_id == dal_return_data[0]["UserID"]
    assert users_list[0].username == dal_return_data[0]["UserName"]
    assert users_list[0].email == dal_return_data[0]["邮箱"]
    assert users_list[0].status == dal_return_data[0]["Status"]
    assert users_list[0].credit == dal_return_data[0]["Credit"]
    assert users_list[0].is_staff == dal_return_data[0]["IsStaff"]
    assert users_list[0].is_verified == dal_return_data[0]["IsVerified"]
    assert users_list[0].major == dal_return_data[0]["Major"]
    assert users_list[0].avatar_url == dal_return_data[0]["AvatarUrl"]
    assert users_list[0].bio == dal_return_data[0]["Bio"]
    assert users_list[0].phone_number == dal_return_data[0]["PhoneNumber"]
    assert users_list[0].join_time == dal_return_data[0]["JoinTime"]

    # Assert attributes of the second user (Pydantic model instance)
    assert users_list[1].user_id == dal_return_data[1]["UserID"]
    assert users_list[1].username == dal_return_data[1]["UserName"]
    assert users_list[1].email == dal_return_data[1]["邮箱"]
    assert users_list[1].status == dal_return_data[1]["Status"]
    assert users_list[1].credit == dal_return_data[1]["Credit"]
    assert users_list[1].is_staff == dal_return_data[1]["IsStaff"]
    assert users_list[1].is_verified == dal_return_data[1]["IsVerified"]
    assert users_list[1].major == dal_return_data[1]["Major"]
    assert users_list[1].avatar_url == dal_return_data[1]["AvatarUrl"]
    assert users_list[1].bio == dal_return_data[1]["Bio"]
    assert users_list[1].phone_number == dal_return_data[1]["PhoneNumber"]
    assert users_list[1].join_time == dal_return_data[1]["JoinTime"]

    # Verify DAL method was called with correct arguments
    mock_user_dal.get_all_users.assert_called_once_with(mock_db_connection, test_admin_id)

@pytest.mark.asyncio
async def test_admin_get_all_users_forbidden(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    test_admin_id = uuid4()

    # Simulate DAL raising ForbiddenError
    mock_user_dal.get_all_users.side_effect = ForbiddenError("Only administrators can view all users.")

    # Call the service function and assert it raises ForbiddenError
    with pytest.raises(ForbiddenError, match="Only administrators can view all users."):
        await user_service.get_all_users(mock_db_connection, test_admin_id)

    # Verify DAL method was called
    mock_user_dal.get_all_users.assert_called_once_with(mock_db_connection, test_admin_id)

# Add test for DALError in get_all_users if needed

# Add tests for set_chat_message_visibility if needed

# Add tests for get_user_password_hash_by_id if needed

# Add tests for admin methods raising NotFoundError, ForbiddenError from DAL