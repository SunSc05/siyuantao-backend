import pytest
import pytest_mock
from httpx import AsyncClient

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from app.services.user_service import UserService
from app.dal.user_dal import UserDAL
from app.schemas.user_schemas import UserRegisterSchema, UserLoginSchema, UserPasswordUpdate, UserProfileUpdateSchema, UserStatusUpdateSchema, UserCreditAdjustmentSchema # Import necessary schemas
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
    """Test successful user creation."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    # Mock password hashing utility (using mock_utils_auth fixture)
    mock_get_password_hash.return_value = "hashed_password"
    
    username = "testuser"
    email = "test@example.com"
    password = "password"
    user_data = UserRegisterSchema(username=username, email=email, password=password, major="Some Major") # Add major for more realistic data

    # Simulate the DAL create_user method returning a dictionary with NewUserID
    test_user_id = uuid4()
    dal_create_return = { 'NewUserID': test_user_id }

    # Simulate the DAL get_user_by_id method returning the full user profile
    dal_get_return = {
        '用户ID': test_user_id,
        '用户名': username,
        '邮箱': email,
        '账户状态': "Active",
        '信用分': 100,
        '是否管理员': False,
        '是否已认证': False,
        '专业': "Some Major", # Match the user_data
        '头像URL': None,
        '个人简介': None,
        '手机号码': None,
        '注册时间': datetime.now()
    }

    # Configure the side effect for mock_user_dal.create_user
    # It should first return the result of sp_CreateUser, then the result of get_user_by_id (called internally by DAL)
    # But since Service calls DAL.create_user, we only need to mock DAL.create_user and DAL.get_user_by_id separately as Service calls them sequentially.
    mock_user_dal.create_user.return_value = dal_get_return # Mock create_user to directly return the full profile
    # The previous approach of mocking side_effect for execute_query was for DAL unit tests.
    # For Service tests, we mock the DAL methods directly.

    # If DAL.create_user internally calls DAL.get_user_by_id, we need to mock get_user_by_id as well IF we were testing DAL.
    # But in Service tests, we mock DAL methods directly.
    # Let's revisit the Service logic: Service calls DAL.create_user, which *might* return NewUserID.
    # But the DAL.create_user method we looked at *already* calls get_user_by_id internally and returns the full profile.
    # So, mocking DAL.create_user to return the full profile directly is correct for Service tests.

    # --- Re-correcting mock logic for test_create_user_success ---
    # Service calls DAL.create_user. DAL.create_user internally calls DAL.get_user_by_id.
    # To test Service, we mock DAL.create_user directly. The mock of DAL.create_user should return what Service expects.
    # Service expects the full user dict back from DAL.create_user.
    mock_user_dal.create_user.return_value = dal_get_return # Simulate DAL.create_user returning the full profile
    # No need to mock mock_user_dal.get_user_by_id separately for this scenario unless Service layer *explicitly* calls get_user_by_id after create_user.
    # Reviewing Service code again... No, Service calls create_user and expects the full object back.
    # The previous logic with mocking get_user_by_id was based on a misunderstanding of Service's dependency flow.

    # Let's go back to the previous logic which seems to better match the Service's interaction with DAL's create_user.
    # Service calls DAL.create_user. DAL.create_user returns the *result* of its internal call to get_user_by_id.
    # So, when mocking DAL.create_user for Service tests, its return_value should be the result of a mocked get_user_by_id.
    # This means mocking both, and making DAL.create_user's mock return the result of DAL.get_user_by_id's mock.
    # This seems overly complicated. A simpler approach: Service calls DAL.create_user. We mock DAL.create_user to return the final expected result directly.

    # Let's check the test failure again: AssertionError: Expected 'get_user_by_id' to be called once. Called 0 times.
    # This strongly suggests the Service layer *does* call get_user_by_id after create_user.
    # Rereading Service.create_user: Yes, it does! It calls `created_user = await self.user_dal.create_user(...)` AND THEN `return created_user`.
    # But the DAL.create_user code I read *also* calls get_user_by_id internally.
    # This indicates a potential discrepancy between the Service layer's assumption about DAL.create_user's return and the actual DAL implementation.
    # However, for unit testing Service, we should mock DAL based on what Service *expects* or *does*, not on DAL's internal implementation details.
    # Service calls DAL.create_user, and then it does something with the result. The test expects DAL.get_user_by_id to be called by Service.
    # This means the flow is: Service calls DAL.create_user -> DAL.create_user returns something that Service uses to call DAL.get_user_by_id.
    # Reread Service code again... there is no explicit call to get_user_by_id *after* calling create_user in the Service's create_user method.
    # The only call to get_user_by_id is *inside* the DAL.create_user method.
    # So the assertion `mock_user_dal.get_user_by_id.assert_called_once_with` in `test_create_user_success` seems incorrect for unit testing Service.
    # It should probably assert that `mock_user_dal.create_user` was called.

    # Let's correct the assertion first based on the Service code's apparent flow (call DAL.create_user and return its result).
    # The `KeyError: '用户ID'` still suggests the returned object doesn't have this key.
    # Let's go back to mocking DAL.create_user to return the full dict and remove the assertion for get_user_by_id.

    # Correct mock for Service test: Mock DAL.create_user to return the final expected user dictionary.
    mock_user_dal.create_user.return_value = dal_get_return # Simulate DAL.create_user returning the full profile directly to Service
    # Remove the assertion about get_user_by_id being called.

    # Call the service method
    created_user = await user_service.create_user(mock_db_connection, user_data)

    print(f"DEBUG: Created user object in test_create_user_success: {created_user}") # Debug print

    # Assert the service returned the expected data
    assert created_user is not None
    # Ensure UUID is converted to string for comparison
    assert str(created_user['用户ID']) == str(test_user_id)
    assert created_user['用户名'] == username
    assert created_user['邮箱'] == email
    assert created_user['账户状态'] == "Active"
    assert created_user['信用分'] == 100
    assert created_user['是否管理员'] is False
    assert created_user['是否已认证'] is False
    assert created_user['专业'] == "Some Major" # Assert the major is included
    assert created_user['头像URL'] is None
    assert created_user['个人简介'] is None
    assert created_user['手机号码'] is None
    assert created_user['注册时间'] is not None
    
    # Verify that the DAL method was called with the correct arguments
    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection, # Verify connection is passed
        username,
        email,
        "hashed_password"
        # Add assertion for major if implemented in create_user DAL signature - it's not currently.
    )
    # Verify password hash utility was called
    mock_get_password_hash.assert_called_once_with(password) # Use mocked utility
    # Remove the incorrect assertion about get_user_by_id
    # mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user creation fails on duplicate username."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    mock_get_password_hash.return_value = "hashed_password"
    user_data = UserRegisterSchema(username="testuser", email="test@example.com", password="password")

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

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user creation fails on duplicate email."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    mock_get_password_hash.return_value = "hashed_password"
    user_data = UserRegisterSchema(username="testuser", email="test@example.com", password="password")

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

@pytest.mark.asyncio
async def test_create_user_dal_error(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user creation fails on other DAL errors."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    mock_get_password_hash.return_value = "hashed_password"
    user_data = UserRegisterSchema(username="testuser", email="test@example.com", password="password")

    # Simulate DAL raising DALError
    mock_user_dal.create_user.side_effect = DALError("Database internal error.")

    with pytest.raises(DALError, match="Database internal error."):
        await user_service.create_user(mock_db_connection, user_data)
    
    mock_user_dal.create_user.assert_called_once_with(
        mock_db_connection,
        user_data.username,
        user_data.email,
        "hashed_password"
    )

@pytest.mark.asyncio
async def test_get_user_profile_by_id_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test getting user profile by ID when user is found."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    # Define the expected return value from the mocked DAL method
    expected_dal_return = {
        "用户ID": test_user_id,
        "用户名": "testuser_found",
        "邮箱": "found@example.com",
        # ... other fields
    }
    mock_user_dal.get_user_by_id.return_value = expected_dal_return
    
    # Call the service method
    user_profile = await user_service.get_user_profile_by_id(mock_db_connection, test_user_id)
    
    # Assert the service returned the expected data
    assert user_profile is not None
    assert user_profile["用户ID"] == str(test_user_id)
    assert user_profile["用户名"] == "testuser_found"
    
    # Verify that the DAL method was called with the correct arguments
    mock_user_dal.get_user_by_id.assert_called_once_with(
        mock_db_connection, # Verify connection is passed
        test_user_id # Verify user ID is passed
    )

@pytest.mark.asyncio
async def test_get_user_profile_by_id_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test getting user profile by ID when user is not found."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    # Simulate DAL returning None for not found
    mock_user_dal.get_user_by_id.return_value = None
    
    # Expect NotFoundError to be raised by the service layer
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found."):
        await user_service.get_user_profile_by_id(mock_db_connection, test_user_id)
        
    # Verify that the DAL method was called
    mock_user_dal.get_user_by_id.assert_called_once_with(
        mock_db_connection,
        test_user_id
    )

# --- Tests for authenticate_user_and_create_token ---
@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for successful user authentication and token creation."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    username = "testuser"
    password = "correctpassword"
    hashed_password = "mock_hashed_password"
    test_user_id = uuid4()

    # Simulate DAL returning user data including password hash
    mock_user_dal.get_user_by_username_with_password.return_value = {
        'UserID': test_user_id,
        'UserName': username,
        'Password': "mock_hashed_password", # Ensure this is a non-None string
        'Status': "Active",
        'IsStaff': False,
        'IsVerified': True
    }

    # Use the mocked utilities from the fixture
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth # Unpack the fixture

    mock_verify_password.return_value = True # Simulate successful password verification
    mock_create_access_token.return_value = "mock_jwt_token" # Simulate token creation

    # Call the service method
    token = await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Assert the service returned the expected token
    assert token == "mock_jwt_token"

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)

    # Verify auth utility functions were called with correct arguments
    mock_verify_password.assert_called_once_with(password, hashed_password)
    # Check the data passed to create_access_token - user_id should be string
    expected_token_data = {"user_id": str(test_user_id), "is_staff": False, "is_verified": True} # UserID should be string in token payload
    mock_create_access_token.assert_called_once_with(
        data=expected_token_data,
        expires_delta=mocker.ANY # We don't need to assert the exact timedelta value
    )

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_invalid_password(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for authentication with invalid password."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    username = "testuser"
    password = "wrongpassword"
    hashed_password = "mock_hashed_password"
    test_user_id = uuid4()

    # Simulate DAL returning user data
    mock_user_dal.get_user_by_username_with_password.return_value = {
        'UserID': test_user_id,
        'UserName': username,
        'Password': hashed_password,
        'Status': "Active",
        'IsStaff': False,
        'IsVerified': True
    }

    # Mock verify_password to return False
    mock_verify_password.return_value = False
    # No need to mock create_access_token as it should not be called

    # Expect AuthenticationError
    with pytest.raises(AuthenticationError, match="用户名或密码不正确"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)

    # Verify verify_password was called
    mock_verify_password.assert_called_once_with(password, hashed_password)
    # Verify create_access_token was NOT called

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for authentication when user is not found."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    username = "nonexistentuser"
    password = "password"

    # Simulate DAL returning None (user not found)
    mock_user_dal.get_user_by_username_with_password.return_value = None

    # No need to mock auth utilities as they should not be called

    # Expect AuthenticationError
    with pytest.raises(AuthenticationError, match="用户名或密码不正确"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)

    # Verify auth utility functions were NOT called
    # You could add explicit asserts like:
    # mocker.patch('app.utils.auth.verify_password', spec=True).assert_not_called()
    # mocker.patch('app.utils.auth.create_access_token', spec=True).assert_not_called()

@pytest.mark.asyncio
async def test_authenticate_user_and_create_token_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for authentication with a disabled account."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    username = "disableduser"
    password = "password"
    hashed_password = "mock_hashed_password"
    test_user_id = uuid4()

    # Simulate DAL returning user data with status Disabled
    mock_user_dal.get_user_by_username_with_password.return_value = {
        'UserID': test_user_id,
        'UserName': username,
        'Password': hashed_password,
        'Status': "Disabled",
        'IsStaff': False,
        'IsVerified': True
    }

    # Mock verify_password to return True (password is correct)
    mock_verify_password.return_value = True
    # No need to mock create_access_token as it should not be called due to disabled status

    # Expect ForbiddenError (since status is Disabled)
    with pytest.raises(ForbiddenError, match="账户已被禁用"):
        await user_service.authenticate_user_and_create_token(mock_db_connection, username, password)

    # Verify DAL method was called
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, username)

    # Verify verify_password was called (Service checks password before status)
    mock_verify_password.assert_called_once_with(password, hashed_password)
    # Verify create_access_token was NOT called


# --- Tests for update_user_profile ---
@pytest.mark.asyncio
async def test_update_user_profile_success_with_updates(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test successful user profile update with changes."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(
        major="New Major",
        bio="Updated bio."
    )
    
    # Define the expected return value from the mocked DAL method (after update)
    expected_dal_return = {
        "用户ID": test_user_id,
        "用户名": "testuser",
        "邮箱": "test@example.com",
        "账户状态": "Active",
        "信用分": 100,
        "是否管理员": False,
        "是否已认证": True,
        "专业": "New Major",
        "头像URL": None,
        "个人简介": "Updated bio.",
        "手机号码": None,
        "注册时间": datetime.now()
    }
    mock_user_dal.update_user_profile.return_value = expected_dal_return
    
    # Call the service method
    updated_user = await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)
    
    # Assert the service returned the expected data
    assert updated_user is not None
    assert str(updated_user['用户ID']) == str(test_user_id)
    assert updated_user['用户名'] == "testuser"
    assert updated_user['邮箱'] == "test@example.com"
    assert updated_user['账户状态'] == "Active"
    assert updated_user['信用分'] == 100
    assert updated_user['是否管理员'] is False
    assert updated_user['是否已认证'] is True
    assert updated_user['专业'] == "New Major"
    assert updated_user['头像URL'] is None
    assert updated_user['个人简介'] == "Updated bio."
    assert updated_user['手机号码'] is None
    assert updated_user['注册时间'] is not None
    
    # Verify that the DAL method was called with the correct arguments
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major="New Major",
        avatar_url=None,
        bio="Updated bio.",
        phone_number=None
    )

@pytest.mark.asyncio
async def test_update_user_profile_success_no_updates(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user profile update when no fields are changed (should return current profile)."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    # Create an update schema with no fields set (exclude_unset=True in model_dump will result in empty dict)
    update_data = UserProfileUpdateSchema()

    # Define the expected return value from get_user_profile_by_id (since no update happens)
    expected_current_profile = {
        "用户ID": test_user_id,
        "用户名": "testuser",
        "邮箱": "test@example.com",
        "账户状态": "Active",
        "信用分": 100,
        "是否管理员": False,
        "是否已认证": True,
        "专业": "Old Major",
        "头像URL": None,
        "个人简介": "Old bio.",
        "手机号码": None,
        "注册时间": datetime.now()
    }
    # Mock get_user_profile_by_id, as the service will call it if update_data is empty
    mock_user_dal.get_user_by_id.return_value = expected_current_profile
    
    # Call the service method with empty update data
    updated_user = await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)
    
    # Assert the service returned the current profile
    assert updated_user is not None
    assert str(updated_user['用户ID']) == str(test_user_id)
    assert updated_user['用户名'] == "testuser"
    assert updated_user['邮箱'] == "test@example.com"
    assert updated_user['账户状态'] == "Active"
    assert updated_user['信用分'] == 100
    assert updated_user['是否管理员'] is False
    assert updated_user['是否已认证'] is True
    assert updated_user['专业'] == "Old Major"
    assert updated_user['头像URL'] is None
    assert updated_user['个人简介'] == "Old bio."
    assert updated_user['手机号码'] is None
    assert updated_user['注册时间'] is not None
    
    # Verify that update_user_profile DAL method was NOT called
    mock_user_dal.update_user_profile.assert_not_called()
    # Verify that get_user_by_id DAL method WAS called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_update_user_profile_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user profile update fails when user is not found."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(major="New Major")

    # Simulate DAL raising NotFoundError
    mock_user_dal.update_user_profile.side_effect = NotFoundError(f"User with ID {test_user_id} not found for update.")

    # Expect NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found for update."):
        await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)
        
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major="New Major",
        avatar_url=None,
        bio=None,
        phone_number=None
    )

@pytest.mark.asyncio
async def test_update_user_profile_duplicate_phone(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user profile update fails on duplicate phone number."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    update_data = UserProfileUpdateSchema(phone_number="1234567890")

    # Simulate DAL raising IntegrityError
    mock_user_dal.update_user_profile.side_effect = IntegrityError("Phone number already in use by another user.")

    # Expect IntegrityError
    with pytest.raises(IntegrityError, match="Phone number already in use by another user."):
        await user_service.update_user_profile(mock_db_connection, test_user_id, update_data)
        
    mock_user_dal.update_user_profile.assert_called_once_with(
        mock_db_connection,
        test_user_id,
        major=None,
        avatar_url=None,
        bio=None,
        phone_number="1234567890"
    )


# --- Tests for update_user_password ---
@pytest.mark.asyncio
async def test_update_user_password_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for successful user password update."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    old_password = "oldpassword"
    new_password = "newpassword"
    old_hashed_password = "old_hashed"
    new_hashed_password = "new_hashed"
    password_update_data = UserPasswordUpdate(old_password=old_password, new_password=new_password)

    # Simulate DAL returning user data with old password hash
    # update_user_password service method first calls get_user_by_id, then get_user_by_username_with_password
    # We need to mock both calls.
    mock_user_dal.get_user_by_id.return_value = {'用户ID': test_user_id, '用户名': "testuser", '邮箱': "test@example.com", '账户状态': "Active", '信用分': 100, '是否管理员': False, '是否已认证': True, '专业': None, '头像URL': None, '个人简介': None, '手机号码': None, '注册时间': datetime.now()}
    mock_user_dal.get_user_by_username_with_password.return_value = {
         'UserID': test_user_id,
         'UserName': "testuser",
         'Password': old_hashed_password,
         'Status': "Active",
         'IsStaff': False,
         'IsVerified': True,
         'Email': "test@example.com"
    }

    # Mock utils.auth functions
    mock_verify_password.return_value = True
    mock_get_password_hash.return_value = new_hashed_password
    mock_user_dal.update_user_password.return_value = True # Simulate successful DAL update

    # Call the service method
    update_success = await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Assert the service returned True
    assert update_success is True

    # Verify DAL methods were called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, "testuser")
    mock_user_dal.update_user_password.assert_called_once_with(mock_db_connection, test_user_id, new_hashed_password)

    # Verify auth utility functions were called
    mock_verify_password.assert_called_once_with(old_password, old_hashed_password)
    mock_get_password_hash.assert_called_once_with(new_password)

@pytest.mark.asyncio
async def test_update_user_password_wrong_old_password(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer test for updating password with incorrect old password."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    old_password = "wrongpassword"
    new_password = "newpassword"
    old_hashed_password = "old_hashed"
    password_update_data = UserPasswordUpdate(old_password=old_password, new_password=new_password)

    # Simulate DAL returning user data with old password hash
    mock_user_dal.get_user_by_id.return_value = {'用户ID': test_user_id, '用户名': "testuser", '邮箱': "test@example.com", '账户状态': "Active", '信用分': 100, '是否管理员': False, '是否已认证': True, '专业': None, '头像URL': None, '个人简介': None, '手机号码': None, '注册时间': datetime.now()}
    mock_user_dal.get_user_by_username_with_password.return_value = {
         'UserID': test_user_id,
         'UserName': "testuser",
         'Password': old_hashed_password,
         'Status': "Active",
         'IsStaff': False,
         'IsVerified': True,
         'Email': "test@example.com"
    }

    # Mock verify_password to return False
    mock_verify_password.return_value = False
    # No need to mock get_password_hash or update_user_password as they should not be called

    # Expect AuthenticationError
    with pytest.raises(AuthenticationError, match="旧密码不正确"):
        await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Verify DAL methods were called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    mock_user_dal.get_user_by_username_with_password.assert_called_once_with(mock_db_connection, "testuser")

    # Verify verify_password was called
    mock_verify_password.assert_called_once_with(old_password, old_hashed_password)
    # Verify other auth utilities and DAL update were NOT called
    # mocker.patch('app.utils.auth.get_password_hash').assert_not_called()
    # mock_user_dal.update_user_password.assert_not_called()

@pytest.mark.asyncio
async def test_update_user_password_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test password update fails when user is not found (first DAL call)."""
    # Unpack the mock_utils_auth tuple
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    password_update_data = UserPasswordUpdate(old_password="oldpassword", new_password="newpassword")

    # Simulate get_user_by_id DAL method raising NotFoundError
    mock_user_dal.get_user_by_id.side_effect = NotFoundError(f"User with ID {test_user_id} not found.")
    # Mock other utilities/DAL methods to ensure they are not called
    mock_user_dal.get_user_by_username_with_password.return_value = None
    # mock_verify_password and mock_get_password_hash are already mocked by the fixture
    # We just need to ensure their return values are not set in a way that bypasses the exception
    # Their default return is None, which is fine as they won't be called.
    mock_user_dal.update_user_password.return_value = False

    # Expect NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found."):
        await user_service.update_user_password(mock_db_connection, test_user_id, password_update_data)

    # Verify only the first DAL method was called
    mock_user_dal.get_user_by_id.assert_called_once_with(mock_db_connection, test_user_id)
    # Verify other methods were NOT called
    mock_user_dal.get_user_by_username_with_password.assert_not_called()
    mock_user_dal.update_user_password.assert_not_called()

# --- Tests for delete_user ---
@pytest.mark.asyncio
async def test_delete_user_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test successful user deletion."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()

    # Simulate DAL returning True on successful deletion
    mock_user_dal.delete_user.return_value = True

    # Call the service method
    delete_success = await user_service.delete_user(mock_db_connection, test_user_id)

    # Assert the service returned True
    assert delete_success is True

    # Verify DAL method was called
    mock_user_dal.delete_user.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_delete_user_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test user deletion fails when user is not found."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()

    # Simulate DAL raising NotFoundError
    mock_user_dal.delete_user.side_effect = NotFoundError(f"User with ID {test_user_id} not found for deletion.")

    # Expect NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {test_user_id} not found for deletion."):
        await user_service.delete_user(mock_db_connection, test_user_id)

    # Verify DAL method was called
    mock_user_dal.delete_user.assert_called_once_with(mock_db_connection, test_user_id)


# --- Tests for request_verification_email ---
@pytest.mark.asyncio
async def test_request_verification_email_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer function to handle request for email verification link.
    Calls DAL and can potentially trigger email sending (TODO).
    """
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    email = "test@example.com"
    test_user_id = uuid4()
    test_token = uuid4()

    # Simulate DAL returning success result
    expected_dal_return = {"VerificationToken": test_token, "UserID": test_user_id, "IsNewUser": True}
    mock_user_dal.request_verification_link.return_value = expected_dal_return

    # Call the service method
    result = await user_service.request_verification_email(mock_db_connection, email)

    # Assert the service returned the expected data
    assert result == expected_dal_return

    # Verify DAL method was called
    mock_user_dal.request_verification_link.assert_called_once_with(mock_db_connection, email)

@pytest.mark.asyncio
async def test_request_verification_email_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test request verification email fails for disabled account."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    email = "disabled@example.com"

    # Simulate DAL raising DALError for disabled account
    mock_user_dal.request_verification_link.side_effect = DALError("Account is disabled.")

    # Expect DALError (or specific service exception if implemented)
    with pytest.raises(DALError, match="Account is disabled."):
        await user_service.request_verification_email(mock_db_connection, email)

    # Verify DAL method was called
    mock_user_dal.request_verification_link.assert_called_once_with(mock_db_connection, email)


# --- Tests for verify_email ---
@pytest.mark.asyncio
async def test_verify_email_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Service layer function to handle email verification with token.
    Calls DAL to verify token.
    """
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_token = UUID('cccccccc-cccc-cccc-cccc-cccccccccccc')
    test_user_id = uuid4()

    # Simulate DAL returning success result
    expected_dal_return = {"UserID": test_user_id, "IsVerified": True}
    mock_user_dal.verify_email.return_value = expected_dal_return

    # Call the service method
    result = await user_service.verify_email(mock_db_connection, test_token)

    # Assert the service returned the expected data
    assert result == expected_dal_return
    assert result["IsVerified"] is True # Ensure IsVerified is True

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)

@pytest.mark.asyncio
async def test_verify_email_invalid_or_expired_token(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test email verification fails with invalid or expired token."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_token = UUID('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee')

    # Simulate DAL raising DALError for invalid/expired token
    mock_user_dal.verify_email.side_effect = DALError("Magic link invalid or expired.")

    # Expect DALError
    with pytest.raises(DALError, match="Magic link invalid or expired."):
        await user_service.verify_email(mock_db_connection, test_token)

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)

@pytest.mark.asyncio
async def test_verify_email_disabled_account(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test email verification fails for disabled account."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_token = UUID('ffffffff-ffff-ffff-ffff-ffffffffffff')

    # Simulate DAL raising DALError for disabled account
    mock_user_dal.verify_email.side_effect = DALError("Account is disabled.")

    # Expect DALError
    with pytest.raises(DALError, match="Account is disabled."):
        await user_service.verify_email(mock_db_connection, test_token)

    # Verify DAL method was called
    mock_user_dal.verify_email.assert_called_once_with(mock_db_connection, test_token)


# --- Tests for get_system_notifications ---
@pytest.mark.asyncio
async def test_get_system_notifications_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test getting system notifications for a user."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    # Define the expected return value from the mocked DAL method
    expected_dal_return = [
        {"通知ID": uuid4(), "标题": "Notification 1", "内容": "Content 1", "是否已读": 0},
        {"通知ID": uuid4(), "标题": "Notification 2", "内容": "Content 2", "是否已读": 1},
    ]
    mock_user_dal.get_system_notifications_by_user_id.return_value = expected_dal_return

    # Call the service method
    notifications = await user_service.get_system_notifications(mock_db_connection, test_user_id)

    # Assert the service returned the expected data
    assert notifications == expected_dal_return

    # Verify DAL method was called
    mock_user_dal.get_system_notifications_by_user_id.assert_called_once_with(mock_db_connection, test_user_id)

@pytest.mark.asyncio
async def test_get_system_notifications_no_notifications(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test getting system notifications when there are none."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    test_user_id = uuid4()
    # Simulate DAL returning an empty list
    mock_user_dal.get_system_notifications_by_user_id.return_value = []

    # Call the service method
    notifications = await user_service.get_system_notifications(mock_db_connection, test_user_id)

    # Assert an empty list is returned
    assert notifications == []

    # Verify DAL method was called
    mock_user_dal.get_system_notifications_by_user_id.assert_called_once_with(mock_db_connection, test_user_id)

# --- Tests for mark_system_notification_as_read ---
@pytest.mark.asyncio
async def test_mark_system_notification_as_read_success(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test marking a system notification as read."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL returning True on success
    mock_user_dal.mark_notification_as_read.return_value = True

    # Call the service method
    mark_success = await user_service.mark_system_notification_as_read(mock_db_connection, notification_id, test_user_id)

    # Assert the service returned True
    assert mark_success is True

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, notification_id, test_user_id)

@pytest.mark.asyncio
async def test_mark_system_notification_as_read_not_found(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test marking a system notification as read fails when notification is not found."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL raising NotFoundError
    mock_user_dal.mark_notification_as_read.side_effect = NotFoundError(f"Notification with ID {notification_id} not found.")

    # Expect NotFoundError
    with pytest.raises(NotFoundError, match=f"Notification with ID {notification_id} not found."):
        await user_service.mark_system_notification_as_read(mock_db_connection, notification_id, test_user_id)

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, notification_id, test_user_id)

@pytest.mark.asyncio
async def test_mark_system_notification_as_read_forbidden(user_service: UserService, mock_user_dal: AsyncMock, mock_db_connection: MagicMock, mock_utils_auth: tuple[MagicMock, MagicMock, MagicMock], mocker: pytest_mock.MockerFixture):
    """Test marking a system notification as read fails due to permission error."""
    # Unpack the mock_utils_auth tuple (though not directly used in this test logic)
    mock_get_password_hash, mock_verify_password, mock_create_access_token = mock_utils_auth

    notification_id = uuid4()
    test_user_id = uuid4()

    # Simulate DAL raising ForbiddenError
    mock_user_dal.mark_notification_as_read.side_effect = ForbiddenError(f"User {test_user_id} does not have permission.")

    # Expect ForbiddenError
    with pytest.raises(ForbiddenError, match=f"User {test_user_id} does not have permission."):
        await user_service.mark_system_notification_as_read(mock_db_connection, notification_id, test_user_id)

    # Verify DAL method was called
    mock_user_dal.mark_notification_as_read.assert_called_once_with(mock_db_connection, notification_id, test_user_id)


# TODO: Add service functions for admin operations (get all users, disable/enable user etc.) 