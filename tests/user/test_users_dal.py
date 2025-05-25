# app/dal/tests/test_users_dal.py
import pytest
import pytest_mock
# import pyodbc # No longer needed for unit tests with mocking
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock # Import mocking tools
# from app.dal.users import (
#     create_user,
#     get_user_by_id,
#     get_user_by_username_with_password,
#     update_user_profile,
#     update_user_password,
#     delete_user,
#     request_verification_link,
#     verify_email
# ) # Replace with UserDAL import
from app.dal.user_dal import UserDAL # Import the new DAL class
from app.dal.connection import get_connection_string # Keep if needed for integration tests, but not for unit tests
from app.exceptions import NotFoundError, IntegrityError, DALError, ForbiddenError
import asyncio # For explicit async calls
from datetime import datetime, timedelta, timezone # Needed for token expiration tests
from app.dal.base import execute_query # Import the execute_query function
import pyodbc # Added for pyodbc.Error

# Configure test database connection string (get from environment or a separate test config)
# TEST_DB_CONN_STR = get_connection_string() # Not needed for mocked unit tests

# Remove the database fixture as we will use mocking
# @pytest.fixture(scope="function", autouse=True)
# async def db_conn_fixture():
#     """Provides a database connection for each test function and rolls back transaction afterwards."""
#     conn = pyodbc.connect(TEST_DB_CONN_STR, autocommit=False)
#     try:
#         yield conn
#         conn.rollback() # Ensure tests do not affect each other
#     finally:
#         conn.close()

# Helper function: Clean up test data (e.g., clear tables before each test if needed)
# Keep if you have integration tests, but remove for pure unit tests
# async def _clean_users_table(conn: pyodbc.Connection):
#     cursor = conn.cursor()
#     # Consider deleting from dependent tables first if foreign keys are strictly enforced
#     # For simplicity, assuming ON DELETE CASCADE or manually handling dependencies if needed
#     cursor.execute("DELETE FROM [User];") # Use the correct table name [User]
#     conn.commit()
#     cursor.close()

# Helper function to set user status (Keep if needed for integration tests)
# async def _set_user_status(conn: pyodbc.Connection, user_id: UUID, status: str):
#     cursor = conn.cursor()
#     cursor.execute("UPDATE [User] SET Status = ? WHERE UserID = ?", (status, user_id))
#     conn.commit()
#     cursor.close()
#     print(f"DEBUG: Set user {user_id} status to {status}.")

# Helper function to set verification token and expiry time (Keep if needed for integration tests)
# async def _set_verification_token(conn: pyodbc.Connection, user_id: UUID, token: UUID, expiry_time: datetime):
#      cursor = conn.cursor()
#      cursor.execute("UPDATE [User] SET VerificationToken = ?, TokenExpireTime = ? WHERE UserID = ?", (token, expiry_time, user_id))
#      conn.commit()
#      cursor.close()
#      print(f"DEBUG: Set verification token {token} and expiry {expiry_time} for user {user_id}.")

# --- Mocking Fixture for DAL ---
# Remove the module-scoped mocker fixture
# @pytest.fixture(scope="module")
# def module_mocker(mocker: pytest_mock.MockerFixture): # Use the function-scoped mocker to create a module-scoped one
#     return mocker

# Modify mock_execute_query to use the default function-scoped mocker
@pytest.fixture(scope="function") # Change scope back to function
def mock_execute_query(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Mock the execute_query dependency."""
    # Patch the execute_query function in app.dal.base
    return mocker.patch('app.dal.base.execute_query', new_callable=AsyncMock)

@pytest.fixture
# Modify the user_dal fixture to accept and use the mock_execute_query fixture
def user_dal(mock_execute_query: AsyncMock): 
    """Provides an instance of UserDAL with mocked dependencies."""
    # Instantiate UserDAL, injecting the mocked execute_query function
    return UserDAL(execute_query_func=mock_execute_query) 

# --- Modified Tests using Mocking ---

@pytest.mark.asyncio
async def test_get_user_by_id_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    test_user_id = UUID('12345678-1234-5678-1234-567812345678')
    # Simulate the database returning a user dictionary
    mock_execute_query.return_value = {
        '用户ID': test_user_id,
        '用户名': "testuser_dal",
        '邮箱': "test_dal@example.com",
        '账户状态': "Active",
        '信用分': 100,
        '是否管理员': False,
        '是否已认证': True,
        '专业': "CS",
        '头像URL': None,
        '个人简介': None,
        '手机号码': None,
        '注册时间': datetime.now()
    }

    # We need a mock connection object to pass to the DAL method
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    user = await user_dal.get_user_by_id(mock_conn, test_user_id)

    assert user is not None
    assert user['用户ID'] == test_user_id
    assert user['用户名'] == "testuser_dal"
    mock_execute_query.assert_called_once_with(
        mock_conn, # Verify conn is passed
        "{CALL sp_GetUserProfileById(?)}",
        (test_user_id,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_get_user_by_id_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    test_user_id = UUID('12345678-1234-5678-1234-567812345678')
    # Simulate the database returning None or a dictionary indicating not found
    # Based on SP and DAL logic, it returns a dict like {'': '用户不存在。'} or None
    mock_execute_query.return_value = {'': '用户不存在。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_execute_query
    user = await user_dal.get_user_by_id(mock_conn, test_user_id)

    assert user is None
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_GetUserProfileById(?)}",
        (test_user_id,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_get_user_by_username_with_password_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    username = "testuser_with_password"
    # Simulate database return including password hash
    mock_execute_query.return_value = {
         'UserID': UUID('12345678-1234-5678-1234-567812345678'),
         'UserName': username,
         'Password': "hashed_password",
         'Status': "Active",
         'IsStaff': False,
         'IsVerified': True,
         'Email': "test_password_dal@example.com"
    }

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    user = await user_dal.get_user_by_username_with_password(mock_conn, username)

    assert user is not None
    assert user['UserName'] == username
    assert user['Password'] == "hashed_password"
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_GetUserByUsernameWithPassword(?)}",
        (username,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_get_user_by_username_with_password_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    username = "nonexistent_user"
    mock_execute_query.return_value = {'': '用户名不能为空。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    user = await user_dal.get_user_by_username_with_password(mock_conn, username)

    assert user is None
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_GetUserByUsernameWithPassword(?)}",
        (username,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_create_user_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    # Arrange
    username = "testuser_dal"
    # email = "test_dal@example.com" # Removed email
    hashed_password = "hashed_password_xyz"
    major = "Engineering"
    phone_number = "5555555555" # Added phone_number

    # Simulate the stored procedure returning the new user ID upon successful creation
    # The SP should return a result set with a 'NewUserID' column
    mock_execute_query.return_value = {'NewUserID': uuid4()}
    
    # Simulate the subsequent query in DAL fetching the complete user data
    # This is what the create_user DAL method now returns after getting the NewUserID
    created_user_data_from_db = {
        "UserID": uuid4(),
        "UserName": username,
        "邮箱": None, # Email is NULL on registration now
        "Status": "Active",
        "Credit": 100,
        "IsStaff": False,
        "IsVerified": False,
        "Major": major,
        "AvatarUrl": None,
        "Bio": None,
        "PhoneNumber": phone_number, # Include phone_number
        "JoinTime": datetime.utcnow(), # Use datetime object
        "StudentID": None, # Include StudentProfile fields as None
        "VerifiedRealName": None,
        "VerifiedDepartment": None,
        "VerifiedClass": None,
        "VerifiedDormitory": None,
        "StudentAuthStatus": None,
    }
    # Mock the second call to execute_query (the fetch by ID) to return the complete user data
    # We need to configure the mock to return different values on consecutive calls
    mock_execute_query.side_effect = [
        {'NewUserID': created_user_data_from_db["UserID"]}, # First call for SP execution
        created_user_data_from_db # Second call for fetching user profile
    ]

    # Act
    # Call the DAL method with updated parameters (no email, with phone_number)
    created_user_data = await user_dal.create_user(mock_execute_query, username, hashed_password, phone_number, major=major)

    # Assert
    # Assert that execute_query was called twice
    assert mock_execute_query.call_count == 2
    
    # Assert the first call to execute_query for the stored procedure
    # The call should include the updated parameters (no email, with phone_number)
    # The order should match the SP definition: username, passwordHash, phoneNumber, major
    expected_sql_sp = "{CALL sp_CreateUser(?, ?, ?, ?)}"
    expected_params_sp = (username, hashed_password, phone_number, major)
    mock_execute_query.call_args_list[0].assert_called_with(expected_sql_sp, expected_params_sp, fetchone=True)

    # Assert the second call to execute_query for fetching the user profile
    # This call happens internally in the DAL's create_user method after getting the NewUserID
    # The SQL and parameters should match the call to sp_GetUserProfileById
    expected_user_id = created_user_data_from_db["UserID"]
    expected_sql_fetch = "{CALL sp_GetUserProfileById(?)}"
    expected_params_fetch = (expected_user_id,)
    mock_execute_query.call_args_list[1].assert_called_with(expected_sql_fetch, expected_params_fetch, fetchone=True)
    
    # Assert the returned data matches the expected dictionary structure
    assert isinstance(created_user_data, dict)
    # Compare essential fields
    assert created_user_data["UserName"] == username
    assert created_user_data.get("邮箱") is None or created_user_data.get("邮箱") == "" # Email is NULL/empty
    assert created_user_data["Major"] == major
    assert created_user_data["PhoneNumber"] == phone_number # Assert phone_number
    # Compare UUID and datetime types (values might be mocked)
    assert isinstance(created_user_data["UserID"], UUID)
    assert isinstance(created_user_data["JoinTime"], datetime)

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_dal: UserDAL, mock_execute_query: AsyncMock):
    # Arrange
    username = "existinguser_dal"
    hashed_password = "hashed_password_def"
    major = "History"
    phone_number = "9998887777"

    # Simulate execute_query raising pyodbc.IntegrityError for duplicate username (from SP)
    mock_execute_query.side_effect = pyodbc.IntegrityError("23000", "[DB-Lib][Error-Message] Duplicate username (SQLState: 23000)")

    # Act & Assert
    with pytest.raises(IntegrityError, match="Username already exists."):
        await user_dal.create_user(mock_execute_query, username, hashed_password, phone_number, major=major)

@pytest.mark.asyncio
async def test_update_user_profile_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_major = "New Major"
    new_bio = "New Bio"
    new_phone_number = "1112223333"

    # Simulate the injected execute_query returning updated user profile directly from the SP call
    mock_execute_query.return_value = {
         'user_id': user_id,
         'username': "testuser",
         'email': "test@example.com",
         'status': "Active",
         'credit': 100,
         'is_staff': False,
         'is_verified': True,
         'major': new_major,
         'avatar_url': None,
         'bio': new_bio,
         'phone_number': new_phone_number,
         'join_time': datetime.utcnow()
    }

    mock_conn = AsyncMock()
    updated_user = await user_dal.update_user_profile(mock_conn, user_id, major=new_major, bio=new_bio, phone_number=new_phone_number)

    assert updated_user is not None
    assert isinstance(updated_user, dict)
    assert updated_user['major'] == new_major
    assert updated_user['bio'] == new_bio
    assert updated_user['phone_number'] == new_phone_number
    assert updated_user['user_id'] == user_id

    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}",
        (user_id, new_major, None, new_bio, new_phone_number),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_major = "New Major"

    # Simulate the injected execute_query returning not found error message from SP
    mock_execute_query.return_value = {'': '用户未找到'}

    mock_conn = AsyncMock()
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for update."):
        await user_dal.update_user_profile(mock_conn, user_id, major=new_major)

    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}",
        (user_id, new_major, None, None, None),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_duplicate_phone(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    phone_number = "1234567890"

    # Simulate the injected execute_query returning duplicate phone error message from SP
    mock_execute_query.return_value = {'': '手机号码已存在'}

    mock_conn = AsyncMock()
    with pytest.raises(IntegrityError, match="Phone number already in use by another user."):
        await user_dal.update_user_profile(mock_conn, user_id, phone_number=phone_number)

    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}",
        (user_id, None, None, None, phone_number),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_password_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_password_hash = "new_hashed_password"

    # Simulate the injected execute_query returning success message
    mock_execute_query.return_value = {'': '密码更新成功'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    update_success = await user_dal.update_user_password(mock_conn, user_id, new_password_hash)

    assert update_success is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_UpdateUserPassword(?, ?)}",
        (user_id, new_password_hash),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_password_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_password_hash = "new_hashed_password"

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '用户不存在。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for password update."):
         await user_dal.update_user_password(mock_conn, user_id, new_password_hash)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_UpdateUserPassword(?, ?)}",
        (user_id, new_password_hash),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_delete_user_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')

    # Simulate the injected execute_query returning rowcount > 0 for successful deletion
    mock_execute_query.return_value = 1

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    delete_success = await user_dal.delete_user(mock_conn, user_id)

    assert delete_success is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_DeleteUser(?)}",
        (user_id,)
        # fetchone=True is not used for DELETE
    )

@pytest.mark.asyncio
async def test_delete_user_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')

    # Simulate the injected execute_query returning rowcount == 0 for not found
    mock_execute_query.return_value = 0

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for deletion."):
         await user_dal.delete_user(mock_conn, user_id)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_DeleteUser(?)}",
        (user_id,)
    )

@pytest.mark.asyncio
async def test_request_verification_link_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    email = "test@example.com"
    test_token = UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    test_user_id = UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')

    # Simulate the injected execute_query returning success result
    mock_execute_query.return_value = {
        'VerificationToken': test_token,
        'UserID': test_user_id,
        'IsNewUser': False
    }

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    linkage_result = await user_dal.request_verification_link(mock_conn, email)

    assert linkage_result is not None
    assert linkage_result['VerificationToken'] == test_token
    assert linkage_result['UserID'] == test_user_id
    assert linkage_result['IsNewUser'] is False
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_RequestMagicLink(?)}",
        (email,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_request_verification_link_disabled_account(user_dal: UserDAL, mock_execute_query: AsyncMock):
    email = "disabled@example.com"

    # Simulate the injected execute_query returning disabled account error
    mock_execute_query.return_value = {'': '您的账户已被禁用，无法登录。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(DALError, match="Account is disabled."):
        await user_dal.request_verification_link(mock_conn, email)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_RequestMagicLink(?)}",
        (email,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_verify_email_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    test_token = UUID('cccccccc-cccc-cccc-cccc-cccccccccccc')
    test_user_id = UUID('dddddddd-dddd-dddd-dddd-dddddddddddd')

    # Simulate the injected execute_query returning success result
    mock_execute_query.return_value = {
        'UserID': test_user_id,
        'IsVerified': True
    }

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    verification_result = await user_dal.verify_email(mock_conn, test_token)

    assert verification_result is not None
    assert verification_result['UserID'] == test_user_id
    assert verification_result['IsVerified'] is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_VerifyMagicLink(?)}",
        (test_token,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_verify_email_invalid_or_expired_token(user_dal: UserDAL, mock_execute_query: AsyncMock):
    test_token = UUID('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee')

    # Simulate the injected execute_query returning invalid/expired token error
    mock_execute_query.return_value = {'': '魔术链接无效或已过期。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(DALError, match="Magic link invalid or expired."):
        await user_dal.verify_email(mock_conn, test_token)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_VerifyMagicLink(?)}",
        (test_token,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_verify_email_disabled_account(user_dal: UserDAL, mock_execute_query: AsyncMock):
    test_token = UUID('ffffffff-ffff-ffff-ffff-ffffffffffff')

    # Simulate the injected execute_query returning disabled account error
    mock_execute_query.return_value = {'': '您的账户已被禁用，无法登录。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(DALError, match="Account is disabled."):
        await user_dal.verify_email(mock_conn, test_token)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_VerifyMagicLink(?)}",
        (test_token,),
        fetchone=True
    )

# Add more tests for edge cases and other methods in UserDAL

# --- New DAL Tests ---

@pytest.mark.asyncio
async def test_set_chat_message_visibility_success(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    message_id = uuid4()
    user_id = uuid4()
    visible_to = "sender"
    is_visible = False

    # Simulate the injected execute_query returning success message
    mock_execute_query.return_value = {'': '消息可见性设置成功'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    success = await user_dal.set_chat_message_visibility(mock_conn, message_id, user_id, visible_to, is_visible)

    assert success is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_SetChatMessageVisibility(?, ?, ?, ?)}",
        (message_id, user_id, visible_to, is_visible),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_set_chat_message_visibility_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    message_id = uuid4()
    user_id = uuid4()
    visible_to = "sender"
    is_visible = False

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '消息不存在。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"Message with ID {message_id} not found."):
        await user_dal.set_chat_message_visibility(mock_conn, message_id, user_id, visible_to, is_visible)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_SetChatMessageVisibility(?, ?, ?, ?)}",
        (message_id, user_id, visible_to, is_visible),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_set_chat_message_visibility_forbidden(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    message_id = uuid4()
    user_id = uuid4()
    visible_to = "sender"
    is_visible = False

    # Simulate the injected execute_query returning forbidden error
    mock_execute_query.return_value = {'': '无权修改此消息的可见性。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(ForbiddenError, match=f"User {user_id} does not have permission to modify visibility of message {message_id}."):
        await user_dal.set_chat_message_visibility(mock_conn, message_id, user_id, visible_to, is_visible)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_SetChatMessageVisibility(?, ?, ?, ?)}",
        (message_id, user_id, visible_to, is_visible),
        fetchone=True
    )

# TODO: Add test for invalid visible_to value

@pytest.mark.asyncio
async def test_change_user_status_success(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()
    admin_id = uuid4()
    new_status = "Disabled"

    # Simulate the injected execute_query returning success message
    mock_execute_query.return_value = {'': '用户状态更新成功。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    success = await user_dal.change_user_status(mock_conn, user_id, new_status, admin_id)

    assert success is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_ChangeUserStatus(?, ?, ?)}",
        (user_id, new_status, admin_id),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_change_user_status_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()
    admin_id = uuid4()
    new_status = "Disabled"

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '用户不存在。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found."):
        await user_dal.change_user_status(mock_conn, user_id, new_status, admin_id)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_ChangeUserStatus(?, ?, ?)}",
        (user_id, new_status, admin_id),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_change_user_status_forbidden(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()
    admin_id = uuid4()
    new_status = "Disabled"

    # Simulate the injected execute_query returning forbidden error
    mock_execute_query.return_value = {'': '无权限执行此操作，只有管理员可以更改用户状态。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(ForbiddenError, match="Only administrators can change user status."):
        await user_dal.change_user_status(mock_conn, user_id, new_status, admin_id)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_ChangeUserStatus(?, ?, ?)}",
        (user_id, new_status, admin_id),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_change_user_status_invalid_status(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()
    admin_id = uuid4()
    new_status = "InvalidStatus"

    # Simulate the injected execute_query returning invalid status error
    mock_execute_query.return_value = {'': '无效的用户状态，状态必须是 Active 或 Disabled。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(DALError, match="Invalid user status provided."):
        await user_dal.change_user_status(mock_conn, user_id, new_status, admin_id)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_ChangeUserStatus(?, ?, ?)}",
        (user_id, new_status, admin_id),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = 10
    reason = "Good behavior"

    # Simulate the injected execute_query returning success message
    mock_execute_query.return_value = {'': '用户信用分调整成功。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    success = await user_dal.adjust_user_credit(mock_conn, user_id, credit_adjustment, admin_id, reason)

    assert success is True
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = -5
    reason = "Violated rule"

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '用户不存在。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found."):
        await user_dal.adjust_user_credit(mock_conn, user_id, credit_adjustment, admin_id, reason)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_forbidden(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = 10
    reason = "Good behavior"

    # Simulate the injected execute_query returning forbidden error
    mock_execute_query.return_value = {'': '无权限执行此操作，只有管理员可以调整用户信用分。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(ForbiddenError, match="Only administrators can adjust user credit."):
        await user_dal.adjust_user_credit(mock_conn, user_id, credit_adjustment, admin_id, reason)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_adjust_user_credit_missing_reason(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = uuid4()
    admin_id = uuid4()
    credit_adjustment = 10
    reason = ""

    # Simulate the injected execute_query returning missing reason error
    mock_execute_query.return_value = {'': '调整信用分必须提供原因。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(DALError, match="Reason for credit adjustment must be provided."):
        await user_dal.adjust_user_credit(mock_conn, user_id, credit_adjustment, admin_id, reason)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}",
        (user_id, credit_adjustment, admin_id, reason),
        fetchone=True
    )

# TODO: Add tests for credit limits (e.g., adjusting to > 100 or < 0) - Requires checking the output of the SP if it returns the new credit

@pytest.mark.asyncio
async def test_get_user_password_hash_by_id_found(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()
    password_hash = "hashed_password"

    # Simulate the injected execute_query returning password hash
    mock_execute_query.return_value = {'Password': password_hash}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    fetched_hash = await user_dal.get_user_password_hash_by_id(mock_conn, user_id)

    assert fetched_hash == password_hash
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_GetUserPasswordHashById(?)}",
        (user_id,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_get_user_password_hash_by_id_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    user_id = uuid4()

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '用户不存在。'}
    mock_conn = AsyncMock()

    # user_dal fixture already provides the DAL instance with mocked execute_query
    fetched_hash = await user_dal.get_user_password_hash_by_id(mock_conn, user_id)

    assert fetched_hash is None
    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_GetUserPasswordHashById(?)}",
        (user_id,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_get_all_users_success(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    test_admin_id = uuid4()
    # Simulate the injected execute_query returning a list of user dictionaries
    mock_execute_query.return_value = [
        {
            '用户ID': uuid4(),
            '用户名': "user1",
            '邮箱': "user1@example.com",
            '账户状态': "Active",
            '信用分': 100,
            '是否管理员': False,
            '是否已认证': True,
            '专业': "CS",
            '头像URL': None,
            '个人简介': None,
            '手机号码': "1111111111",
            '注册时间': datetime.now()
        },
        {
            '用户ID': uuid4(),
            '用户名': "user2",
            '邮箱': "user2@example.com",
            '账户状态': "Disabled",
            '信用分': 50,
            '是否管理员': False,
            '是否已认证': False,
            '专业': "Physics",
            '头像URL': "url2",
            '个人简介': "Bio 2",
            '手机号码': "0987654321",
            '注册时间': datetime.now()
        }
    ]

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    users_list = await user_dal.get_all_users(mock_conn, test_admin_id)

    assert isinstance(users_list, list)
    assert len(users_list) == 2
    assert all(isinstance(user, dict) for user in users_list)
    # Check that the injected execute_query was called once
    mock_execute_query.assert_called_once_with(
        mock_conn, # Verify conn is passed
        "{CALL sp_GetAllUsers(?)}",
        (test_admin_id,),
        fetchall=True
    )

@pytest.mark.asyncio
async def test_admin_get_all_users_forbidden(user_dal: UserDAL, mock_execute_query: AsyncMock, mocker):
    test_non_admin_id = uuid4()
    # Simulate the injected execute_query raising an error for insufficient privileges
    # Using side_effect to raise an exception
    mock_execute_query.side_effect = ForbiddenError("无权限执行此操作，只有管理员可以查看所有用户。") # Simulate the error message from SP/DB

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    
    # Use a try...except block to more explicitly handle the expected exception
    try:
        await user_dal.get_all_users(mock_conn, test_non_admin_id)
        # If the above line doesn't raise an exception, the test should fail
        pytest.fail("Expected ForbiddenError but no exception was raised.")
    except ForbiddenError as e:
        # Assert that the correct exception was raised with the expected message
        assert str(e) == "无权限执行此操作，只有管理员可以查看所有用户。"
    except Exception as e:
        # Catch any other unexpected exceptions and fail the test
        pytest.fail(f"Expected ForbiddenError but caught unexpected exception: {type(e).__name__}: {e}")

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn, # Verify conn is passed
        "{CALL sp_GetAllUsers(?)}",
        (test_non_admin_id,),
        fetchall=True
    )

