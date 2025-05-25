# app/dal/user_dal.py
import pyodbc
from app.dal.base import execute_query # Keep for type hinting, but not for direct calls within methods
from app.exceptions import NotFoundError, IntegrityError, DALError, ForbiddenError
from uuid import UUID
import logging
from typing import Optional, Dict, Any
# from datetime import datetime # 如果存储过程返回 datetime 对象

logger = logging.getLogger(__name__)

class UserDAL:
    def __init__(self, execute_query_func): # Accept execute_query as a dependency
        # DAL 类本身不持有连接，连接由 Service 层或 API 层的依赖注入提供
        # Store the injected execute_query function
        self._execute_query = execute_query_func

    async def get_user_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> dict | None:
        """从数据库获取指定 ID 的用户（获取完整资料）。"""
        logger.debug(f"DAL: Attempting to get user by ID: {user_id}") # Add logging
        # 调用 sp_GetUserProfileById 存储过程
        sql = "{CALL sp_GetUserProfileById(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            logger.debug(f"DAL: sp_GetUserProfileById for ID {user_id} returned: {result}") # Add logging
            if result and isinstance(result, dict) and '用户不存在。' in result.values(): # 根据存储过程的错误返回判断
                 logger.debug(f"DAL: User with ID {user_id} not found according to SP.") # Add logging
                 return None # 用户不存在
            if result and isinstance(result, dict): return result
            logger.warning(f"DAL: sp_GetUserProfileById for ID {user_id} returned unexpected type: {type(result)}") # Add logging
            return None # Handle cases where result is not a dict as expected
        except Exception as e:
            logger.error(f"DAL: Error getting user by ID {user_id}: {e}") # Add logging
            raise DALError(f"Database error while fetching user profile: {e}") from e

    async def get_user_by_username_with_password(self, conn: pyodbc.Connection, username: str) -> dict | None:
        """从数据库获取指定用户名的用户（包含密码哈希），用于登录。"""
        logger.debug(f"DAL: Attempting to get user by username with password: {username}") # Add logging
        # 调用 sp_GetUserByUsernameWithPassword 存储过程
        sql = "{CALL sp_GetUserByUsernameWithPassword(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (username,), fetchone=True)
            logger.debug(f"DAL: sp_GetUserByUsernameWithPassword for {username} returned: {result}") # Add logging
            if result and isinstance(result, dict) and '用户名不能为空。' in result.values(): # 根据存储过程的错误返回判断
                logger.debug(f"DAL: User with username {username} not found according to SP.") # Add logging
                return None # 用户名为空
            if result and isinstance(result, dict): return result
            logger.warning(f"DAL: sp_GetUserByUsernameWithPassword for {username} returned unexpected type: {type(result)}") # Add logging
            return None
        except Exception as e:
            logger.error(f"DAL: Error getting user by username {username}: {e}") # Add logging
            raise DALError(f"Database error while fetching user by username: {e}") from e

    async def create_user(self, conn: pyodbc.Connection, username: str, hashed_password: str, phone_number: str, major: Optional[str] = None) -> dict:
        """在数据库中创建新用户并返回其数据。"""
        logger.debug(f"DAL: Attempting to create user: {username}")
        sql = "{CALL sp_CreateUser(?, ?, ?, ?)}"
        try:
            # 调用 sp_CreateUser 存储过程
            logger.debug(f"DAL: Executing sp_CreateUser for {username} with phone: {phone_number}, major: {major}")
            result = await self._execute_query(conn, sql, (username, hashed_password, phone_number, major), fetchone=True)
            logger.debug(f"DAL: sp_CreateUser for {username} returned raw result: {result}")

            # 1. 检查结果是否为 None
            if result is None:
                logger.error(f"DAL: sp_CreateUser for {username} returned None")
                raise DALError("User creation failed: No response from database")

            # 2. 检查结果是否为字典类型
            if not isinstance(result, dict):
                logger.error(f"DAL: sp_CreateUser for {username} returned non-dict result: {type(result)}")
                raise DALError(f"User creation failed: Unexpected response type from database: {type(result)}")

            # 3. 检查错误消息
            error_message = None
            if '' in result:  # 检查空键
                error_message = result['']
            if 'Error' in result and result['Error']:
                error_message = result['Error']
            if 'Message' in result and result['Message']:
                error_message = result['Message']

            if error_message:
                logger.debug(f"DAL: sp_CreateUser for {username} returned message: {error_message}")
                # 检查是否是成功消息
                if '用户创建成功' in error_message or '创建成功' in error_message:
                    logger.info(f"DAL: User {username} created successfully")
                # 检查是否是错误消息
                elif '用户名已存在' in error_message or 'Duplicate username' in error_message:
                    logger.warning(f"DAL: Username {username} already exists")
                    raise IntegrityError("Username already exists.")
                elif '手机号已存在' in error_message or 'Duplicate phone' in error_message:
                    logger.warning(f"DAL: Phone number {phone_number} already exists")
                    raise IntegrityError("Phone number already exists.")
                else:
                    logger.error(f"DAL: Unexpected error message during user creation: {error_message}")
                    raise DALError(f"Stored procedure error during user creation: {error_message}")

            # 4. 检查是否包含 NewUserID
            if 'NewUserID' not in result:
                logger.error(f"DAL: sp_CreateUser for {username} returned result without NewUserID: {result}")
                raise DALError("User creation failed: No user ID returned from database")

            # 5. 获取新用户ID并验证
            new_user_id = result['NewUserID']
            if not new_user_id:
                logger.error(f"DAL: sp_CreateUser for {username} returned empty NewUserID")
                raise DALError("User creation failed: Empty user ID returned from database")

            logger.info(f"DAL: User {username} created with NewUserID: {new_user_id}. Fetching full info.")
            
            # 6. 获取完整用户信息
            full_user_info = await self.get_user_by_id(conn, new_user_id)
            logger.debug(f"DAL: get_user_by_id for new user {new_user_id} returned: {full_user_info}")
            
            if not full_user_info:
                logger.error(f"DAL: Failed to retrieve full user info after creation for ID: {new_user_id}")
                raise DALError(f"Failed to retrieve full user info after creation for ID: {new_user_id}")

            logger.info(f"DAL: Full info retrieved for new user: {username}")
            return full_user_info

        except IntegrityError:
            raise
        except pyodbc.IntegrityError as e:
            logger.error(f"DAL: pyodbc.IntegrityError during user creation for {username}: {e}")
            error_message = str(e)
            if 'Duplicate username' in error_message or '用户名已存在' in error_message:
                raise IntegrityError("Username already exists.") from e
            elif 'Duplicate phone' in error_message or '手机号已存在' in error_message:
                raise IntegrityError("Phone number already exists.") from e
            else:
                logger.error(f"DAL: Unexpected Integrity Error during user creation: {e}")
                raise DALError(f"Database integrity error during user creation: {e}") from e
        except Exception as e:
            logger.error(f"DAL: Generic Error creating user {username}: {e}")
            raise DALError(f"Database error during user creation: {e}") from e

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, *, major: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None, phone_number: Optional[str] = None) -> dict | None:
        """更新现有用户的个人资料，返回更新后的用户数据。"""
        logger.debug(f"DAL: Attempting to update profile for user ID: {user_id}") # Add logging
        sql = "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}"
        try:
            logger.debug(f"DAL: Executing sp_UpdateUserProfile for ID {user_id}") # Add logging
            result = await self._execute_query(
                conn, sql,
                (user_id, major, avatar_url, bio, phone_number),
                fetchone=True
            )
            logger.debug(f"DAL: sp_UpdateUserProfile for ID {user_id} returned: {result}") # Add logging

            if result and isinstance(result, dict): # Assuming SP returns the updated user data or a success indicator
                error_message = result.get('')
                if 'Error' in result and result['Error']:
                    error_message = result['Error']

                if error_message:
                    logger.warning(f"DAL: sp_UpdateUserProfile for ID {user_id} returned error: {error_message}") # Add logging
                    if '用户未找到' in error_message:
                        raise NotFoundError(f"User with ID {user_id} not found for update.")
                    # Prioritize checking for the specific phone number duplicate error message from SP
                    elif '手机号码已存在' in error_message or '手机号已存在' in error_message:
                         raise IntegrityError("Phone number already in use by another user.")
                    else:
                         # If it's an error from SP but not specific to user not found or duplicate phone
                         raise DALError(f"Stored procedure error during profile update: {error_message}")

                logger.debug(f"DAL: Profile update for ID {user_id} successful.") # Add logging
                return result # Return the dictionary fetched by execute_query(fetchone=True) which should be the updated user data
            elif result is None:
                 logger.debug(f"DAL: Profile update for ID {user_id} returned None.") # Add logging
                 return None # Or raise NotFoundError if SP indicates user not found by returning None

            # If result is not None and not a dict with an error message, assume success and return the data
            logger.warning(f"DAL: Profile update for ID {user_id} returned unexpected non-dict result: {result}") # Add logging

        except NotFoundError as e:
             logger.error(f"DAL: NotFoundError during profile update for ID {user_id}: {e}") # Add logging
             raise e # Re-raise NotFoundError caught from our checks
        except IntegrityError as e:
             logger.error(f"DAL: IntegrityError during profile update for ID {user_id}: {e}") # Add logging
             raise e # Re-raise IntegrityError caught from our checks (duplicate phone)
        except pyodbc.IntegrityError as e:
             # Catch pyodbc.IntegrityError raised by the driver
             logger.error(f"DAL: pyodbc.IntegrityError during profile update for ID {user_id}: {e}") # Add logging
             error_message = str(e)
             # Check for specific error messages related to duplicate phone number from the driver
             # These might be different depending on the database and driver configuration
             error_message_lower = error_message.lower()
             # Example patterns for duplicate key errors, specifically looking for phone number context
             if ('duplicate key' in error_message_lower or '违反唯一约束' in error_message_lower) and ('phone' in error_message_lower or '手机' in error_message_lower):
                 raise IntegrityError("Phone number already in use by another user.") from e
             else:
                 # Re-raise other IntegrityErrors as DALError or a more specific error
                 logger.error(f"DAL: Unexpected pyodbc.IntegrityError during profile update: {e}")
                 raise DALError(f"Database integrity error during profile update: {e}") from e
        except Exception as e:
            logger.error(f"DAL: Generic Error updating user profile for {user_id}: {e}") # Add logging
            # Catch any other unexpected exceptions during the DAL operation
            raise DALError(f"Database error during user profile update: {e}") from e

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, hashed_password: str) -> bool:
        """更新用户密码。"""
        logger.debug(f"DAL: Attempting to update password for user ID: {user_id}") # Add logging
        sql = "{CALL sp_UpdateUserPassword(?, ?)}"
        try:
            # 调用 sp_UpdateUserPassword 存储过程
            # Use the injected execute_query function
            logger.debug(f"DAL: Executing sp_UpdateUserPassword for ID {user_id}") # Add logging
            result = await self._execute_query(conn, sql, (user_id, hashed_password), fetchone=True)
            logger.debug(f"DAL: sp_UpdateUserPassword for ID {user_id} returned: {result}") # Add logging

            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                 logger.warning(f"DAL: Password update failed for ID {user_id}: User not found according to SP.") # Add logging
                 raise NotFoundError(f"User with ID {user_id} not found for password update.")
            if result and isinstance(result, dict) and '密码更新失败。' in result.values():
                 logger.error(f"DAL: Password update failed for ID {user_id} according to SP.") # Add logging
                 raise DALError("Password update failed in stored procedure.")
            if result and isinstance(result, dict) and '密码更新成功' in result.values():
                 logger.info(f"DAL: Password updated successfully for user ID: {user_id}") # Add logging
                 return True

            # 意外情况
            if result is not None and isinstance(result, dict): # Ensure result is a dict if not None
                 logger.warning(f"DAL: sp_UpdateUserPassword for ID {user_id} returned unexpected dict result: {result}") # Add logging
            else:
                 logger.warning(f"DAL: sp_UpdateUserPassword for ID {user_id} returned unexpected non-dict result: {result}") # Add logging
            return False

        except NotFoundError:
             raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"DAL: Generic Error updating user password for user {user_id}: {e}") # Add logging
            raise DALError(f"Database error during user password update: {e}") from e

    # New method: Get user password hash by ID
    async def get_user_password_hash_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> str | None:
        """根据用户 ID 获取密码哈希。"""
        logger.debug(f"DAL: Attempting to get password hash for user ID: {user_id}") # Add logging
        sql = "{CALL sp_GetUserPasswordHashById(?)}"
        try:
            # Use the injected execute_query function
            logger.debug(f"DAL: Executing sp_GetUserPasswordHashById for ID {user_id}") # Add logging
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            logger.debug(f"DAL: sp_GetUserPasswordHashById for ID {user_id} returned: {result}") # Add logging
            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                logger.debug(f"DAL: Password hash not found for ID {user_id}: User not found according to SP.") # Add logging
                return None # User not found
            if result and isinstance(result, dict) and 'Password' in result:
                logger.debug(f"DAL: Password hash found for ID {user_id}.") # Add logging
                return result['Password']
            logger.warning(f"DAL: sp_GetUserPasswordHashById for ID {user_id} returned unexpected result: {result}") # Add logging
            return None
        except Exception as e:
            logger.error(f"DAL: Generic Error getting password hash for user ID {user_id}: {e}") # Add logging
            raise DALError(f"Database error while fetching password hash: {e}") from e

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """删除用户。"""
        logger.debug(f"DAL: Attempting to delete user with ID: {user_id}") # Add logging
        # 调用 sp_DeleteUser 存储过程 (这个SP在你的sql_scripts里没有找到，假设存在且逻辑正确)
        # 如果 sp_DeleteUser 不存在，需要创建
        # 暂时保留原有的假设调用，并在文档中提示需要实现或确认此SP
        sql = "{CALL sp_DeleteUser(?)}"
        try:
            logger.debug(f"DAL: Executing sp_DeleteUser for ID: {user_id}") # Add logging
            # Use the injected execute_query function
            # execute_query 默认返回 rowcount 对于 DELETE 操作
            # 存储过程 sp_DeleteUser 应该返回 rowcount 或者抛出异常
            # 如果存储过程使用 RAISERROR 并且没有返回行，execute_query 可能会捕获到异常或者返回 None/0 rowcount
            # 假设 SP 抛出异常或者返回0 rowcount 表示未找到用户
            result = await self._execute_query(conn, sql, (user_id,))
            # execute_query 返回的结果类型需要根据实际实现确定，可能是 rowcount 或其他

            # 这里的逻辑依赖于 execute_query 和 sp_DeleteUser 的具体实现
            # 如果 execute_query 在 RAISERROR 时抛出异常，那 NotFoundError 会被捕获
            # 如果 execute_query 返回 rowcount 且 SP 在用户不存在时返回 0 rowcount
            if result == 0:
                 raise NotFoundError(f"User with ID {user_id} not found for deletion.")
            # 假设成功删除返回非零 rowcount 或者 execute_query 返回 True
            # 根据 execute_query 的文档，对于非 SELECT 语句，成功时返回 rowcount
            if result is not None and result > 0:
                 return True # 表示删除成功
            
            # Unexpected case
            logger.warning(f"DAL: Unexpected result from sp_DeleteUser for user {user_id}: {result}")
            return False

        except NotFoundError:
            raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"DAL: Error deleting user with ID {user_id}: {e}")
            raise DALError(f"Database error during user deletion: {e}") from e

    async def request_verification_link(self, conn: pyodbc.Connection, email: str) -> dict:
         """请求邮箱验证链接，调用sp_RequestMagicLink。"""
         sql = "{CALL sp_RequestMagicLink(?)}"
         try:
             # Use the injected execute_query function
             result = await self._execute_query(conn, sql, (email,), fetchone=True)

             if result and isinstance(result, dict) and '您的账户已被禁用，无法登录。' in result.values():
                  raise DALError("Account is disabled.") # 或者自定义更精确的异常

             # 存储过程返回 VerificationToken, UserID, IsNewUser
             if result and isinstance(result, dict) and all(key in result for key in ['VerificationToken', 'UserID', 'IsNewUser']):
                  return result

             raise DALError("Request verification link failed: Unexpected response from stored procedure.")

         except Exception as e:
             logger.error(f"Error requesting verification link for email {email}: {e}")
             raise DALError(f"Database error during requesting verification link: {e}") from e

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
         """验证邮箱，调用sp_VerifyMagicLink。"""
         sql = "{CALL sp_VerifyMagicLink(?)}"
         try:
             # Use the injected execute_query function
             result = await self._execute_query(conn, sql, (token,), fetchone=True)

             if result and isinstance(result, dict) and '魔术链接无效或已过期。' in result.values():
                  raise DALError("Magic link invalid or expired.") # 或者自定义更精确的异常
             if result and isinstance(result, dict) and '您的账户已被禁用，无法登录。' in result.values():
                  raise DALError("Account is disabled.")

             # 存储过程返回 UserID, IsVerified
             if result and isinstance(result, dict) and all(key in result for key in ['UserID', 'IsVerified']):
                  return result

             raise DALError("Verify email failed: Unexpected response from stored procedure.")

         except Exception as e:
             logger.error(f"Error verifying email with token {token}: {e}")
             raise DALError(f"Database error during email verification: {e}") from e

    async def get_system_notifications_by_user_id(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """获取某个用户的系统通知列表。"""
        sql = "{CALL sp_GetSystemNotificationsByUserId(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchall=True)
            if result and isinstance(result, list) and any(isinstance(row, dict) and '用户不存在。' in row.values() for row in result):
                 return [] # User not found or no notifications
            if result and isinstance(result, list): return result
            return []
        except Exception as e:
            logger.error(f"Error getting system notifications for user {user_id}: {e}")
            raise DALError(f"Database error while fetching system notifications: {e}") from e

    async def mark_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """标记系统通知为已读。"""
        sql = "{CALL sp_MarkNotificationAsRead(?, ?)}"
        try:
            # Use the injected execute_query function
            # MarkNotificationAsRead SP should return a result indicating success or failure
            result = await self._execute_query(conn, sql, (notification_id, user_id), fetchone=True)

            if result and isinstance(result, dict) and '通知不存在。' in result.values():
                 raise NotFoundError(f"Notification with ID {notification_id} not found.")
            if result and isinstance(result, dict) and '无权标记此通知为已读。' in result.values():
                 raise ForbiddenError(f"User {user_id} does not have permission to mark notification {notification_id} as read.")
            if result and isinstance(result, dict) and '通知标记为已读成功。' in result.values():
                 return True

            # Unexpected case
            if result is not None and isinstance(result, dict):
                 logger.warning(f"DAL: Unexpected result from sp_MarkNotificationAsRead for notification {notification_id}, user {user_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError) as e:
            raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error marking notification {notification_id} as read for user {user_id}: {e}")
            raise DALError(f"Database error while marking notification as read: {e}") from e

    async def set_chat_message_visibility(self, conn: pyodbc.Connection, message_id: UUID, user_id: UUID, visible_to: str, is_visible: bool) -> bool:
        """设置聊天消息对发送者或接收者的可见性（逻辑删除）。"""
        sql = "{CALL sp_SetChatMessageVisibility(?, ?, ?, ?)}"
        try:
            # Use the injected execute_query function
            # sp_SetChatMessageVisibility returns a result indicating success or failure or raises errors
            # It returns a success message like '消息可见性设置成功' or errors for not found/permission denied
            result = await self._execute_query(conn, sql, (message_id, user_id, visible_to, is_visible), fetchone=True)

            if result and isinstance(result, dict) and '消息不存在。' in result.values():
                 raise NotFoundError(f"Message with ID {message_id} not found.")
            if result and isinstance(result, dict) and '无权修改此消息的可见性。' in result.values():
                 raise ForbiddenError(f"User {user_id} does not have permission to modify visibility of message {message_id}.")
            if result and isinstance(result, dict) and '消息可见性设置成功' in result.values():
                 return True

            # Unexpected case
            if result is not None and isinstance(result, dict):
                 logger.warning(f"DAL: Unexpected result from sp_SetChatMessageVisibility for message {message_id}, user {user_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error setting message visibility for message {message_id}, user {user_id}: {e}")
            raise DALError(f"Database error while setting message visibility: {e}") from e

    # New admin methods for user management
    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """管理员禁用/启用用户账户。"""
        sql = "{CALL sp_ChangeUserStatus(?, ?, ?)}"
        try:
            # Use the injected execute_query function
            # sp_ChangeUserStatus returns a success message or raises errors
            result = await self._execute_query(conn, sql, (user_id, new_status, admin_id), fetchone=True)

            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                 raise NotFoundError(f"User with ID {user_id} not found.")
            if result and isinstance(result, dict) and '无权限执行此操作，只有管理员可以更改用户状态。' in result.values():
                 raise ForbiddenError("Only administrators can change user status.")
            if result and isinstance(result, dict) and '无效的用户状态，状态必须是 Active 或 Disabled。' in result.values():
                 raise DALError("Invalid user status provided.") # Should be caught by validation layer, but check anyway
            if result and isinstance(result, dict) and '用户状态更新成功。' in result.values():
                 return True

            # Unexpected case
            if result is not None and isinstance(result, dict):
                 logger.warning(f"DAL: Unexpected result from sp_ChangeUserStatus for user {user_id}, admin {admin_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error changing user status for user {user_id}, admin {admin_id}: {e}")
            raise DALError(f"Database error while changing user status: {e}") from e

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """管理员手动调整用户信用分。"""
        sql = "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}"
        try:
            # Use the injected execute_query function
            # sp_AdjustUserCredit returns a success message or raises errors
            result = await self._execute_query(conn, sql, (user_id, credit_adjustment, admin_id, reason), fetchone=True)

            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                 raise NotFoundError(f"User with ID {user_id} not found.")
            if result and isinstance(result, dict) and '无权限执行此操作，只有管理员可以调整用户信用分。' in result.values():
                 raise ForbiddenError("Only administrators can adjust user credit.")
            if result and isinstance(result, dict) and '调整信用分必须提供原因。' in result.values():
                 raise DALError("Reason for credit adjustment must be provided.") # Should be caught by validation layer, but check anyway
            if result and isinstance(result, dict) and '用户信用分调整成功。' in result.values():
                 return True

            # Unexpected case
            if result is not None and isinstance(result, dict):
                 logger.warning(f"DAL: Unexpected result from sp_AdjustUserCredit for user {user_id}, admin {admin_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error adjusting user credit for user {user_id}, admin {admin_id}: {e}")
            raise DALError(f"Database error while adjusting user credit: {e}") from e

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[dict]:
        """管理员获取所有用户列表。"""
        sql = "{CALL sp_GetAllUsers(?)}"
        try:
            # 调用 sp_GetAllUsers 存储过程
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (admin_id,), fetchall=True)

            # 存储过程在无权限或错误时会抛出 RAISERROR， execute_query 应该会捕获并转换为异常
            # 如果返回一个空列表，表示没有用户（或用户不存在，SP处理了）
            if result is None:
                 return [] # No users found or unexpected empty result

            if not isinstance(result, list) or (result and not isinstance(result[0], dict)):
                 # Handle unexpected result format
                 logger.error(f"DAL: Unexpected result format from sp_GetAllUsers for admin {admin_id}: {result}")
                 raise DALError("Database error while fetching all users: Unexpected data format.")

            # 存储过程应该返回用户列表，其结构与 sp_GetUserProfileById 相似
            return result # Returns a list of user dictionaries

        except Exception as e:
            # Catch any exception during query execution, including those from RAISERROR
            logger.error(f"DAL: Error getting all users for admin {admin_id}: {e}")
            # 根据 SP 的错误消息类型，可能需要更细致的异常处理
            if "无权限执行此操作" in str(e):
                 raise ForbiddenError(str(e)) # 将数据库权限错误转换为应用层异常
            if "管理员不存在" in str(e): # 假设 SP 也可能检查管理员是否存在
                 raise NotFoundError(str(e)) # 管理员不存在也算一种"无权限"

            raise DALError(f"Database error while fetching all users: {e}") from e 