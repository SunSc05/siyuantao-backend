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
    username = "new_user_dal"
    email = "new_dal@example.com"
    password_hash = "new_hashed_pass"
    new_user_id = UUID('87654321-4321-8765-4321-876543210987')

    # Simulate sp_CreateUser to return NewUserID
    # The create_user DAL method internally calls get_user_by_id, which uses the injected execute_query.
    # So we need to mock the side_effect for the injected mock_execute_query.
    mock_execute_query.side_effect = [
        { 'NewUserID': new_user_id }, # First call for create_user SP
        { # Second call for get_user_by_id
            '用户ID': new_user_id,
            '用户名': username,
            '邮箱': email,
            '账户状态': "Active",
            '信用分': 100,
            '是否管理员': False,
            '是否已认证': False,
            '专业': None,
            '头像URL': None,
            '个人简介': None,
            '手机号码': None,
            '注册时间': datetime.now()
        }
    ]

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    created_user = await user_dal.create_user(mock_conn, username, email, password_hash)

    assert created_user is not None
    assert created_user['用户ID'] == new_user_id
    assert created_user['用户名'] == username
    assert created_user['邮箱'] == email
    # Check that execute_query was called twice:
    # Once for sp_CreateUser
    mock_execute_query.call_args_list[0].assert_called_with(
        mock_conn,
        "{CALL sp_CreateUser(?, ?, ?)}",
        (username, email, password_hash),
        fetchone=True
    )
    # Once for get_user_by_id (called internally by create_user)
    mock_execute_query.call_args_list[1].assert_called_with(
         mock_conn,
         "{CALL sp_GetUserProfileById(?)}",
         (new_user_id,),
         fetchone=True
    )

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_dal: UserDAL, mock_execute_query: AsyncMock):
    username = "duplicate_user"
    email = "some@example.com"
    password_hash = "pass"

    # Simulate the injected execute_query returning duplicate error
    mock_execute_query.return_value = {'': '用户名已存在'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(IntegrityError, match="Username already exists."):
        await user_dal.create_user(mock_conn, username, email, password_hash)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_CreateUser(?, ?, ?)}",
        (username, email, password_hash),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_dal: UserDAL, mock_execute_query: AsyncMock):
    username = "some_user"
    email = "duplicate@example.com"
    password_hash = "pass"

    # Simulate the injected execute_query returning duplicate error
    mock_execute_query.return_value = {'': '邮箱已存在'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(IntegrityError, match="Email already exists."):
        await user_dal.create_user(mock_conn, username, email, password_hash)

    # Verify the injected execute_query was called
    mock_execute_query.assert_called_once_with(
        mock_conn,
        "{CALL sp_CreateUser(?, ?, ?)}",
        (username, email, password_hash),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_success(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_major = "New Major"
    new_bio = "New Bio"

    # Simulate the injected execute_query returning updated user profile
    # The update_user_profile DAL method calls get_user_by_id internally, so mock the side_effect.
    mock_execute_query.side_effect = [
        { # First call for update_user_profile SP
             '用户ID': user_id,
             '用户名': "testuser",
             '邮箱': "test@example.com",
             '账户状态': "Active",
             '信用分': 100,
             '是否管理员': False,
             '是否已认证': True,
             '专业': new_major,
             '头像URL': None,
             '个人简介': new_bio,
             '手机号码': None,
             '注册时间': datetime.now()
        },
        # If the first call only returned success message and not the full profile,
        # the DAL method calls get_user_by_id, which is also mocked by mock_execute_query.
        # Add a mock return for get_user_by_id here if needed based on DAL logic flow.
        # For now, assuming the first SP call is mocked to return the full profile.
        { # Second call for get_user_by_id (fallback in DAL if SP doesn't return full profile)
             '用户ID': user_id,
             '用户名': "testuser", # Username remains the same
             '邮箱': "test@example.com", # Email remains the same
             '账户状态': "Active", # Status remains the same
             '信用分': 100, # Credit remains the same
             '是否管理员': False, # IsStaff remains the same
             '是否已认证': True, # IsVerified remains the same
             '专业': new_major, # Updated major
             '头像URL': None, # Avatar URL remains None
             '个人简介': new_bio, # Updated bio
             '手机号码': None, # Phone number remains None
             '注册时间': datetime.now() # Join time remains the same
        }
    ]

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    updated_user = await user_dal.update_user_profile(mock_conn, user_id, major=new_major, bio=new_bio)

    assert updated_user is not None
    assert updated_user['专业'] == new_major
    assert updated_user['个人简介'] == new_bio
    # Verify the injected execute_query was called twice with correct arguments
    assert mock_execute_query.call_count == 2
    mock_execute_query.call_args_list[0].assert_called_with(
        mock_conn,
        "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}",
        (user_id, new_major, None, new_bio, None),
        fetchone=True
    )
    mock_execute_query.call_args_list[1].assert_called_with(
        mock_conn,
        "{CALL sp_GetUserProfileById(?)}",
        (user_id,),
        fetchone=True
    )

@pytest.mark.asyncio
async def test_update_user_profile_not_found(user_dal: UserDAL, mock_execute_query: AsyncMock):
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    new_major = "New Major"

    # Simulate the injected execute_query returning not found error
    mock_execute_query.return_value = {'': '用户不存在。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(NotFoundError, match=f"User with ID {user_id} not found for update."):
        await user_dal.update_user_profile(mock_conn, user_id, major=new_major)

    # Verify the injected execute_query was called
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

    # Simulate the injected execute_query returning duplicate error
    mock_execute_query.return_value = {'': '此手机号码已被其他用户使用。'}

    mock_conn = AsyncMock()
    # user_dal fixture already provides the DAL instance with mocked execute_query
    with pytest.raises(IntegrityError, match="Phone number already in use by another user."):
        await user_dal.update_user_profile(mock_conn, user_id, phone_number=phone_number)

    # Verify the injected execute_query was called
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

