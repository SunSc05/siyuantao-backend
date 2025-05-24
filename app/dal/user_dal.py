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
        # 调用 sp_GetUserProfileById 存储过程
        sql = "{CALL sp_GetUserProfileById(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            if result and isinstance(result, dict) and '用户不存在。' in result.values(): # 根据存储过程的错误返回判断
                 return None # 用户不存在
            if result and isinstance(result, dict): return result
            return None # Handle cases where result is not a dict as expected
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            raise DALError(f"Database error while fetching user profile: {e}") from e

    async def get_user_by_username_with_password(self, conn: pyodbc.Connection, username: str) -> dict | None:
        """从数据库获取指定用户名的用户（包含密码哈希），用于登录。"""
        # 调用 sp_GetUserByUsernameWithPassword 存储过程
        sql = "{CALL sp_GetUserByUsernameWithPassword(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (username,), fetchone=True)
            if result and isinstance(result, dict) and '用户名不能为空。' in result.values(): # 根据存储过程的错误返回判断
                return None # 用户名为空
            if result and isinstance(result, dict): return result
            return None
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            raise DALError(f"Database error while fetching user by username: {e}") from e

    async def create_user(self, conn: pyodbc.Connection, username: str, email: str, hashed_password: str) -> dict:
        """在数据库中创建新用户并返回其数据。"""
        sql = "{CALL sp_CreateUser(?, ?, ?)}"
        try:
            # 调用 sp_CreateUser 存储过程
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (username, email, hashed_password), fetchone=True)

            if result and isinstance(result, dict) and '用户名已存在' in result.values():
                raise IntegrityError("Username already exists.")
            if result and isinstance(result, dict) and '邮箱已存在' in result.values():
                raise IntegrityError("Email already exists.")
            if result and isinstance(result, dict) and '用户创建失败' in result.values():
                 raise DALError("User creation failed in stored procedure.")

            # sp_CreateUser 返回新用户的 NewUserID，需要再次查询获取完整信息
            if result and isinstance(result, dict) and 'NewUserID' in result:
                 new_user_id = result['NewUserID']
                 # 再次查询获取完整信息，使用类内部的方法 (该方法也会使用注入的 execute_query)
                 full_user_info = await self.get_user_by_id(conn, new_user_id)
                 if full_user_info:
                     return full_user_info
                 else:
                     # 这通常不应该发生，除非紧接着查询失败
                     raise DALError(f"Failed to retrieve full user info after creation for ID: {new_user_id}")

            raise DALError("User creation failed: Unexpected response from stored procedure.")

        except IntegrityError:
            raise # Re-raise the IntegrityError
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            raise DALError(f"Database error during user creation: {e}") from e

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, major: str = None, avatar_url: str = None, bio: str = None, phone_number: str = None) -> dict | None:
        """更新用户个人资料。"""
        sql = "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}"
        try:
            # 调用 sp_UpdateUserProfile 存储过程
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id, major, avatar_url, bio, phone_number), fetchone=True)

            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                raise NotFoundError(f"User with ID {user_id} not found for update.")
            if result and isinstance(result, dict) and '此手机号码已被其他用户使用。' in result.values():
                 raise IntegrityError("Phone number already in use by another user.")
            if result and isinstance(result, dict) and '用户信息更新完成并查询成功' in result.values(): # SP 的额外返回
                 # 需要再次查询获取更新后的完整用户信息，或者修改SP使其直接返回完整信息
                 # 如果SP的返回包含了用户字段，直接返回即可
                 # 如果SP只返回成功消息，则需要再次调用 get_user_by_id
                 # 这里假设SP返回了更新后的用户数据
                 # 检查返回是否是用户数据而不是仅有的成功消息
                 if result and isinstance(result, dict) and '用户ID' in result: # 检查是否包含用户profile字段
                     return result
                 else:
                     # 如果SP只返回了成功消息，则重新查询，使用类内部的方法
                     updated_user_info = await self.get_user_by_id(conn, user_id)
                     return updated_user_info

            # 如果没有抛出错误且有返回但不是预期的错误或成功消息，可能是意外情况
            if result and isinstance(result, dict): # Ensure result is a dict if not None
                 logger.warning(f"Unexpected response from sp_UpdateUserProfile for user {user_id}: {result}")
                 # 尝试重新获取用户数据作为回退，使用类内部的方法
                 updated_user_info = await self.get_user_by_id(conn, user_id)
                 return updated_user_info

            # 如果没有任何返回，且没有抛出错误，可能是用户存在但没有字段更新
            # 此时认为更新成功，返回用户当前信息，使用类内部的方法
            return await self.get_user_by_id(conn, user_id)

        except (NotFoundError, IntegrityError) as e:
            raise e # Re-raise NotFoundError or IntegrityError
        except Exception as e:
            logger.error(f"Error updating user profile for user {user_id}: {e}")
            raise DALError(f"Database error during user profile update: {e}") from e

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, hashed_password: str) -> bool:
        """更新用户密码。"""
        sql = "{CALL sp_UpdateUserPassword(?, ?)}"
        try:
            # 调用 sp_UpdateUserPassword 存储过程
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id, hashed_password), fetchone=True)

            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                 raise NotFoundError(f"User with ID {user_id} not found for password update.")
            if result and isinstance(result, dict) and '密码更新失败。' in result.values():
                 raise DALError("Password update failed in stored procedure.")
            if result and isinstance(result, dict) and '密码更新成功' in result.values():
                 return True

            # 意外情况
            if result is not None and isinstance(result, dict): # Ensure result is a dict if not None
                 logger.warning(f"Unexpected response from sp_UpdateUserPassword for user {user_id}: {result}")
            return False

        except NotFoundError:
             raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"Error updating user password for user {user_id}: {e}")
            raise DALError(f"Database error during user password update: {e}") from e

    # New method: Get user password hash by ID
    async def get_user_password_hash_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> str | None:
        """根据用户 ID 获取密码哈希。"""
        sql = "{CALL sp_GetUserPasswordHashById(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            if result and isinstance(result, dict) and '用户不存在。' in result.values():
                return None # User not found
            if result and isinstance(result, dict) and 'Password' in result:
                return result['Password']
            return None
        except Exception as e:
            logger.error(f"Error getting user password hash by ID {user_id}: {e}")
            raise DALError(f"Database error while fetching password hash: {e}") from e

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """删除用户。"""
        # 调用 sp_DeleteUser 存储过程 (这个SP在你的sql_scripts里没有找到，假设存在且逻辑正确)
        # 如果 sp_DeleteUser 不存在，需要创建
        # 暂时保留原有的假设调用，并在文档中提示需要实现或确认此SP
        sql = "{CALL sp_DeleteUser(?)}"
        try:
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
            logger.warning(f"Unexpected result from sp_DeleteUser for user {user_id}: {result}")
            return False

        except NotFoundError:
            raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"Error deleting user with ID {user_id}: {e}")
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
                 logger.warning(f"Unexpected result from sp_MarkNotificationAsRead for notification {notification_id}, user {user_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError) as e:
            raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read for user {user_id}: {e}")
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
                 logger.warning(f"Unexpected result from sp_SetChatMessageVisibility for message {message_id}, user {user_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"Error setting message visibility for message {message_id}, user {user_id}: {e}")
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
                 logger.warning(f"Unexpected result from sp_ChangeUserStatus for user {user_id}, admin {admin_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"Error changing user status for user {user_id}, admin {admin_id}: {e}")
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
                 logger.warning(f"Unexpected result from sp_AdjustUserCredit for user {user_id}, admin {admin_id}: {result}")
            return False

        except (NotFoundError, ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"Error adjusting user credit for user {user_id}, admin {admin_id}: {e}")
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
                 logger.error(f"Unexpected result format from sp_GetAllUsers for admin {admin_id}: {result}")
                 raise DALError("Database error while fetching all users: Unexpected data format.")

            # 存储过程应该返回用户列表，其结构与 sp_GetUserProfileById 相似
            return result # Returns a list of user dictionaries

        except Exception as e:
            # Catch any exception during query execution, including those from RAISERROR
            logger.error(f"Error getting all users for admin {admin_id}: {e}")
            # 根据 SP 的错误消息类型，可能需要更细致的异常处理
            if "无权限执行此操作" in str(e):
                 raise ForbiddenError(str(e)) # 将数据库权限错误转换为应用层异常
            if "管理员不存在" in str(e): # 假设 SP 也可能检查管理员是否存在
                 raise NotFoundError(str(e)) # 管理员不存在也算一种"无权限"

            raise DALError(f"Database error while fetching all users: {e}") from e 