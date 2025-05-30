# app/dal/tests/test_users_dal.py
import pytest
import pytest_mock
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock
from app.dal.user_dal import UserDAL # Import the new DAL class
from app.dal.connection import get_connection_string # Keep if needed for integration tests, but not for unit tests
from app.exceptions import NotFoundError, IntegrityError, DALError, ForbiddenError
import asyncio # For explicit async calls
from datetime import datetime, timedelta, timezone # Needed for token expiration tests
from app.dal.base import execute_query # Import the execute_query function
import pyodbc # Added for pyodbc.Error

# Ensure the fixture scope is function level for isolation
@pytest.fixture(scope="function")
def mock_execute_query(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Fixture for a mock execute_query function."""
    return AsyncMock()

@pytest.fixture
# Modify the user_dal fixture to accept and use the mock_execute_query fixture
def user_dal(mock_execute_query: AsyncMock) -> UserDAL: # Added type hint
    """Fixture to create a UserDAL instance with a mocked execute_query function."""
    # Instantiate UserDAL with the mocked execute_query_func
    return UserDAL(execute_query_func=mock_execute_query)

# Add a mock for the database connection that DAL methods now expect
@pytest.fixture
def mock_db_connection() -> MagicMock:
    """Fixture for a mock database connection."""
    # Use autospec to ensure the mock behaves like a real pyodbc.Connection
    return MagicMock(spec=pyodbc.Connection)

# --- Modified Tests using Mocking ---

@pytest.mark.asyncio
async def test_get_user_by_id_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test fetching a user by ID when the user exists."""
    user_id = uuid4()
    # Simulate the execute_query returning a single user dictionary
    mock_user_data = {
        'UserID': str(user_id),
        'Username': 'testuser',
        'Email': 'test@example.com',
        'Status': 'Active',
        'Credit': 100,
        'IsStaff': False,
        'IsSuperAdmin': False,
        'IsVerified': True,
        'Major': 'Computer Science',
        'AvatarURL': None,
        'Bio': 'A test user.',
        'PhoneNumber': '1234567890',
        'JoinTime': datetime.now(timezone.utc) # Use datetime.now() with timezone.utc
    }
    mock_execute_query.return_value = mock_user_data

    # Call the DAL method, passing the mock connection
    user = await user_dal.get_user_by_id(mock_db_connection, user_id) # Pass mock_db_connection

    # Assert that the method returned the expected dictionary
    assert user == mock_user_data

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetUserProfileById(?)}",
        (user_id,), # Pass UUID object directly
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_get_user_by_id_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test fetching a user by ID when the user does not exist."""
    user_id = uuid4()
    # Simulate the execute_query returning None (no user found)
    mock_execute_query.return_value = None

    # Call the DAL method, passing the mock connection
    user = await user_dal.get_user_by_id(mock_db_connection, user_id) # Pass mock_db_connection

    # Assert that the method returned None
    assert user is None

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetUserProfileById(?)}",
        (user_id,), # Pass UUID object directly
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_get_user_by_username_with_password_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test fetching a user with password by username when the user exists."""
    username = 'testuser'
    # Simulate the execute_query returning a single user dictionary including password hash
    mock_user_data = {
        'UserID': str(uuid4()),
        'Username': username,
        'PasswordHash': 'hashedpassword',
        'IsStaff': False, # Added IsStaff
        'IsVerified': True, # Added IsVerified
        'Status': 'Active' # Added Status
    }
    mock_execute_query.return_value = mock_user_data

    # Call the DAL method, passing the mock connection
    user = await user_dal.get_user_by_username_with_password(mock_db_connection, username) # Pass mock_db_connection

    # Assert that the method returned the expected dictionary
    assert user == mock_user_data

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetUserByUsernameWithPassword(?)}",
        (username,), # Pass username as string
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_get_user_by_username_with_password_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test fetching a user with password by username when the user does not exist."""
    username = 'nonexistentuser'
    # Simulate the execute_query returning None (no user found)
    mock_execute_query.return_value = None

    # Call the DAL method, passing the mock connection
    user = await user_dal.get_user_by_username_with_password(mock_db_connection, username) # Pass mock_db_connection

    # Assert that the method returned None
    assert user is None

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetUserByUsernameWithPassword(?)}",
        (username,), # Pass username as string
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_create_user_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful user creation."""
    # Arrange
    username = 'newuser'
    hashed_password = 'hashedpassword'
    phone_number = '9876543210'
    major = 'Physics'

    # Simulate the SP returning the new user's ID (or success indicator)
    # Assuming SP returns a dictionary with UserID on success
    new_user_id = uuid4()
    mock_execute_query.return_value = {'NewUserID': str(new_user_id)}

    # Act
    # Call the DAL method, passing the mock connection and parameters
    result = await user_dal.create_user(mock_db_connection, username, hashed_password, phone_number, major) # Pass mock_db_connection

    # Assert
    assert isinstance(result, dict)
    assert UUID(result['NewUserID']) == new_user_id

    # Verify the injected execute_query was called with the correct parameters
    # Verify the injected execute_query was called twice
    assert mock_execute_query.call_count == 2

    # Verify the first call (for sp_CreateUser)
    first_call_args, first_call_kwargs = mock_execute_query.call_args_list[0]
    assert first_call_args[0] == mock_db_connection
    assert first_call_args[1] == "{CALL sp_CreateUser(?, ?, ?, ?)}"
    assert first_call_args[2] == (username, hashed_password, phone_number, major)
    assert first_call_kwargs == {'fetchone': True}

    # Verify the second call (for sp_GetUserProfileById) - checks that get_user_by_id was called
    second_call_args, second_call_kwargs = mock_execute_query.call_args_list[1]
    assert second_call_args[0] == mock_db_connection
    # Note: The exact format of the second call might depend on how get_user_by_id is implemented
    # Assuming get_user_by_id uses {CALL sp_GetUserProfileById(?)}
    assert second_call_args[1] == "{CALL sp_GetUserProfileById(?)}"
    assert second_call_args[2] == (new_user_id,)
    assert second_call_kwargs == {'fetchone': True}

@pytest.mark.asyncio
async def test_create_user_duplicate_username(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test user creation with a duplicate username (simulating IntegrityError)."""
    # Arrange
    username = 'existinguser'
    hashed_password = 'hashedpassword'
    phone_number = '1122334455'
    major = 'Chemistry'

    # Simulate the SP returning an error indicating duplicate username
    # Assuming SP returns a dictionary with an error message and/or code
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '用户名已存在。'}

    # Act & Assert: Expecting IntegrityError with a specific message
    # The DAL should translate the SP error message to the IntegrityError detail.
    with pytest.raises(IntegrityError, match="Username already exists."):
         # Pass mock_db_connection and parameters
        await user_dal.create_user(mock_db_connection, username, hashed_password, phone_number, major) # Pass mock_db_connection

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_CreateUser(?, ?, ?, ?)}",
        (username, hashed_password, phone_number, major), # Pass parameters
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful user profile update."""
    user_id = uuid4()
    major = 'New Major'
    avatar_url = 'http://example.com/avatar.jpg'
    bio = 'Updated bio'
    phone_number = '1112223333'
    email = 'updated@example.com'

    # Simulate the SP returning the updated user data
    mock_updated_user_data = {
        'UserID': str(user_id),
        'Username': 'testuser',
        'Email': email,
        'Status': 'Active',
        'Credit': 100,
        'IsStaff': False,
        'IsSuperAdmin': False,
        'IsVerified': True,
        'Major': major,
        'AvatarURL': avatar_url,
        'Bio': bio,
        'PhoneNumber': phone_number,
        'JoinTime': datetime.now(timezone.utc) # Use datetime.now() with timezone.utc
    }
    mock_execute_query.return_value = mock_updated_user_data

    # Call the DAL method
    updated_user = await user_dal.update_user_profile(
        mock_db_connection, # Pass mock_db_connection
        user_id,
        major=major,
        avatar_url=avatar_url,
        bio=bio,
        phone_number=phone_number,
        email=email
    )

    # Assert the method returned the updated user data
    assert updated_user == mock_updated_user_data

    # Verify the injected execute_query was called
    # Parameters should be passed as UUIDs or strings
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?, ?)}",
        (user_id, major, avatar_url, bio, phone_number, email), # Pass UUID object directly
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_update_user_profile_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test updating a user profile when the user does not exist."""
    user_id = uuid4()

    # Simulate the SP returning None or an error indicating not found
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '用户未找到。'} # Simulate error dictionary

    # Call the DAL method
    # The DAL should raise NotFoundError if SP returns user not found error.
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for update."):
         # Pass mock_db_connection
        await user_dal.update_user_profile(mock_db_connection, user_id, major='New Major') # Pass mock_db_connection

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?, ?)}",
        (user_id, 'New Major', None, None, None, None), # Pass UUID object and other params
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_duplicate_phone(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test updating user profile with a duplicate phone number (simulating IntegrityError)."""
    user_id = uuid4()
    phone_number = '1234567890'

    # Simulate the SP returning an error indicating duplicate phone number
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '手机号码已存在。'}

    # Act & Assert: Expecting IntegrityError with a specific message
    # The DAL should translate the SP error message to the IntegrityError detail.
    with pytest.raises(IntegrityError, match="Phone number already in use by another user."):
         # Pass mock_db_connection and parameters
        await user_dal.update_user_profile(mock_db_connection, user_id, phone_number=phone_number) # Pass mock_db_connection

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?, ?)}",
        (user_id, None, None, None, phone_number, None), # Pass UUID object and phone_number
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_password_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful user password update."""
    user_id = uuid4()
    hashed_password = 'newhashedpassword'

    # Simulate the SP returning success indicator (e.g., OperationResultCode 0)
    # Assuming SP returns a dictionary like {'OperationResultCode': 0, '': '密码更新成功。'}
    mock_execute_query.return_value = {'OperationResultCode': 0, '': '密码更新成功。'} # Simulate success dictionary

    # Call the DAL method
    # The DAL method should return True on success, not raise an error.
    success = await user_dal.update_user_password(mock_db_connection, user_id, hashed_password) # Pass mock_db_connection

    # Assert that the method returned True
    assert success is True

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_UpdateUserPassword(?, ?)}",
        (user_id, hashed_password), # Pass UUID object
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_update_user_password_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test updating a user password when the user does not exist."""
    user_id = uuid4()
    hashed_password = 'newhashedpassword'

    # Simulate the SP returning not found error (e.g., OperationResultCode -1)
    # Assuming SP returns a dictionary like {'OperationResultCode': -1, '': '用户未找到。'}
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '用户未找到。'} # Simulate error dictionary

    # Call the DAL method and expect NotFoundError
    # The DAL maps SP errors to specific exception messages. Match the English message.
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for password update."):
         # Pass mock_db_connection and parameters
        await user_dal.update_user_password(mock_db_connection, user_id, hashed_password) # Pass mock_db_connection

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_UpdateUserPassword(?, ?)}",
        (user_id, hashed_password), # Pass UUID object
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_delete_user_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful user deletion."""
    user_id = uuid4()

    # Simulate the SP returning success indicator (e.g., OperationResultCode 0)
    mock_execute_query.return_value = {'OperationResultCode': 0, '': '用户删除成功。'} # Simulate success dictionary

    # Call the DAL method
    success = await user_dal.delete_user(mock_db_connection, user_id) # Pass mock_db_connection

    # Assert that the method returned True
    assert success is True

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_DeleteUser(?)}",
        (user_id,), # Pass UUID object
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_delete_user_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test deleting a user when the user does not exist."""
    # Correctly format the UUID string
    user_id = uuid4()

    # Simulate the SP returning not found error (e.g., OperationResultCode -1)
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '用户未找到。'} # Simulate error dictionary

    # Call the DAL method and expect NotFoundError
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for deletion."):
         # Pass mock_db_connection and parameters
        await user_dal.delete_user(mock_db_connection, user_id) # Pass mock_db_connection

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_DeleteUser(?)}",
        (user_id,), # Pass UUID object
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_request_verification_link_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful request for a verification link."""
    # Arrange
    user_id = uuid4()
    email = "test@example.edu.cn"
    # Simulate the SP returning the magic link token and expiration
    magic_link_token = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15) # Use datetime.now() and timedelta
    mock_execute_query.return_value = {
        'VerificationToken': str(magic_link_token),
        'ExpiresAt': expires_at
    }

    # Act
    # Pass mock_db_connection and parameters
    result = await user_dal.request_verification_link(mock_db_connection, user_id=user_id, email=email)

    # Assert
    assert result is not None
    assert isinstance(result, dict)
    assert UUID(result['VerificationToken']) == magic_link_token
    # Allow some tolerance for datetime comparison due to potential minor differences
    assert result['ExpiresAt'] >= expires_at - timedelta(seconds=1) # Use timedelta
    assert result['ExpiresAt'] <= expires_at + timedelta(seconds=1) # Use timedelta

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_RequestMagicLink(?, ?)}", # Corrected SP name
        (email, user_id), # Corrected parameter order and passed UUID object
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successful user credit adjustment by admin."""
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = 50
    reason = "Bonus for good behavior"

    # Simulate the SP returning success indicator (e.g., OperationResultCode 0)
    # Ensure the mock returns a dictionary with OperationResultCode 0 and a success message.
    mock_execute_query.return_value = {'OperationResultCode': 0, '': '信用分调整成功。'} # Simulate success dictionary with code

    # Call the DAL method
    # The DAL method should return True on success, not raise an error.
    success = await user_dal.adjust_user_credit(mock_db_connection, user_id, credit_adjustment, admin_id, reason) # Pass mock_db_connection

    # Assert that the method returned True
    assert success is True

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason), # Pass UUID objects
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_not_found(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test adjusting user credit when the user does not exist."""
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = -20
    reason = "Penalty for violation"

    # Simulate the SP returning not found error (e.g., OperationResultCode -1)
    # Ensure the mock returns a dictionary with OperationResultCode -1 and a user not found message.
    mock_execute_query.return_value = {'OperationResultCode': -1, '': '用户未找到。'} # Simulate error dictionary with code

    # Call the DAL method and expect NotFoundError
    # The DAL maps SP errors to specific exception messages. Match the English message.
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for credit adjustment."):
         # Pass mock_db_connection and parameters
        await user_dal.adjust_user_credit(mock_db_connection, user_id, credit_adjustment, admin_id, reason) # Pass mock_db_connection

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason), # Pass UUID objects
        fetchone=True # Assuming SP returns a single row result
    )

@pytest.mark.asyncio
async def test_get_all_users_success(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test successfully getting all users by admin."""
    admin_id = uuid4()

    # Simulate the SP returning a list of user dictionaries
    mock_users_data = [
        {
            'UserID': str(uuid4()),
            'Username': 'user1',
            'Email': 'user1@example.com',
            'Status': 'Active',
            'Credit': 100,
            'IsStaff': False,
            'IsSuperAdmin': False,
            'IsVerified': True,
            'Major': 'Math',
            'AvatarURL': None,
            'Bio': None,
            'PhoneNumber': '1111111111',
            'JoinTime': datetime.now(timezone.utc) # Use datetime.now() with timezone.utc
        },
        {
            'UserID': str(uuid4()),
            'Username': 'admin1',
            'Email': 'admin1@example.com',
            'Status': 'Active',
            'Credit': 200,
            'IsStaff': True,
            'IsSuperAdmin': False,
            'IsVerified': True,
            'Major': None,
            'AvatarURL': None,
            'Bio': 'Site admin',
            'PhoneNumber': '2222222222',
            'JoinTime': datetime.now(timezone.utc) # Use datetime.now() with timezone.utc
        }
    ]
    mock_execute_query.return_value = mock_users_data

    # Call the DAL method
    users = await user_dal.get_all_users(mock_db_connection, admin_id) # Pass mock_db_connection

    # Assert the method returned the expected list of dictionaries
    assert users == mock_users_data

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetAllUsers(?)}",
        (admin_id,), # Pass UUID object
        fetchall=True # Assuming SP returns multiple rows
    )

@pytest.mark.asyncio
async def test_admin_get_all_users_forbidden(
    user_dal: UserDAL, # Update type hint
    mock_execute_query: AsyncMock,
    mock_db_connection: MagicMock # Inject mock_db_connection fixture
):
    """Test getting all users when the user is not an admin (simulating ForbiddenError)."""
    admin_id = uuid4() # A regular user ID

    # Simulate the injected execute_query returning forbidden error (OperationResultCode -2)
    # Ensure the mock returns a dictionary with OperationResultCode -2 and a forbidden message.
    mock_execute_query.return_value = {'OperationResultCode': -2, '': '只有超级管理员可以查看所有用户。'} # Simulate error dictionary with code

    # Expect a ForbiddenError with a specific message from the DAL
    # The DAL maps SP errors to specific exception messages. Match the English message.
    with pytest.raises(ForbiddenError, match="Only administrators can view all users"): # Using the specific ForbiddenError message from DAL
         # Pass mock_db_connection and parameters
        await user_dal.get_all_users(mock_db_connection, admin_id) # Pass mock_db_connection

    # Verify the injected execute_query was called with the correct parameters
    mock_execute_query.assert_called_once_with(
        mock_db_connection, # Verify conn is passed
        "{CALL sp_GetAllUsers(?)}",
        (admin_id,), # Pass UUID object
        fetchall=True
    )

