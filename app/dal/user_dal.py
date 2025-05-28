# app/dal/user_dal.py
import pyodbc
# Keep for type hinting, but not for direct calls within methods
from app.dal.base import execute_query
from app.exceptions import NotFoundError, IntegrityError, DALError, ForbiddenError
from uuid import UUID
import logging
from typing import Optional, Dict, Any
# from datetime import datetime # 如果存储过程返回 datetime 对象

logger = logging.getLogger(__name__)


class UserDAL:
    def __init__(self, execute_query_func):  # Accept execute_query as a dependency
        # DAL 类本身不持有连接，连接由 Service 层或 API 层的依赖注入提供
        # Store the injected execute_query function
        self._execute_query = execute_query_func

    async def get_user_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> dict | None:
        """从数据库获取指定 ID 的用户（获取完整资料）。"""
        logger.debug(
            f"DAL: Attempting to get user by ID: {user_id}")  # Add logging
        # 调用 sp_GetUserProfileById 存储过程
        sql = "{CALL sp_GetUserProfileById(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            # Add logging
            logger.debug(
                f"DAL: sp_GetUserProfileById for ID {user_id} returned: {result}")
            # Check for specific messages indicating user not found, handle potential variations
            if result and isinstance(result, dict):
                if '用户不存在。' in result.values() or 'User not found.' in result.values() or (result.get('OperationResultCode') == -1 if result.get('OperationResultCode') is not None else False):
                    # Add logging
                    logger.debug(
                        f"DAL: User with ID {user_id} not found according to SP.")
                    return None  # 用户不存在
                 # If it's a dictionary and not an error message, return the result
                return result
            # Add logging
            logger.warning(
                f"DAL: sp_GetUserProfileById for ID {user_id} returned unexpected type or None: {result}")
            return None  # Handle cases where result is not a dict as expected

        except Exception as e:
            # Add logging
            logger.error(f"DAL: Error getting user by ID {user_id}: {e}")
            raise DALError(
                f"Database error while fetching user profile: {e}") from e

    async def get_user_by_username_with_password(self, conn: pyodbc.Connection, username: str) -> dict | None:
        """从数据库获取指定用户名的用户（包含密码哈希），用于登录。"""
        logger.debug(
            # Add logging
            f"DAL: Attempting to get user by username with password: {username}")
        # 调用 sp_GetUserByUsernameWithPassword 存储过程
        sql = "{CALL sp_GetUserByUsernameWithPassword(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (username,), fetchone=True)
            # Add logging
            logger.debug(
                f"DAL: sp_GetUserByUsernameWithPassword for {username} returned: {result}")
            if result and isinstance(result, dict):
                 if '用户名不能为空。' in result.values() or 'Username cannot be empty.' in result.values():  # 根据存储过程的错误返回判断
                     # Add logging
                     logger.debug(
                         f"DAL: User with username {username} not found according to SP.")
                     return None  # 用户名为空
                 return result  # Assuming a dict result is the user data
            # Add logging
            logger.warning(
                f"DAL: sp_GetUserByUsernameWithPassword for {username} returned unexpected type or None: {result}")
            return None
        except Exception as e:
            # Add logging
            logger.error(
                f"DAL: Error getting user by username {username}: {e}")
            raise DALError(
                f"Database error while fetching user by username: {e}") from e

    async def create_user(self, conn: pyodbc.Connection, username: str, hashed_password: str, phone_number: str, major: Optional[str] = None) -> dict:
        """在数据库中创建新用户并返回其数据。"""
        logger.debug(f"DAL: Attempting to create user: {username}")
        sql = "{CALL sp_CreateUser(?, ?, ?, ?)}"
        try:
            # 调用 sp_CreateUser 存储过程
            logger.debug(
                f"DAL: Executing sp_CreateUser for {username} with phone: {phone_number}, major: {major}")
            # sp_CreateUser returns a single row with NewUserID and potentially Message/Error
            result = await self._execute_query(conn, sql, (username, hashed_password, phone_number, major), fetchone=True)
            logger.debug(
                f"DAL: sp_CreateUser for {username} returned raw result: {result}")

            # 1. 检查结果是否为 None 或非字典类型
            if not result or not isinstance(result, dict):
                logger.error(
                    f"DAL: sp_CreateUser for {username} returned invalid result: {result}")
                raise DALError(
                    f"User creation failed: Unexpected response from database: {result}")

            # 2. 优先检查是否包含 NewUserID (Assuming this is the primary success indicator from SP)
            new_user_id = result.get('NewUserID')

            if new_user_id:
                 # If NewUserID is present, consider it success and proceed to validation and fetching full info.
                 # Message field is ignored as an error in this case.

                 # 3. Validate NewUserID is a valid UUID string or UUID object
                 if not isinstance(new_user_id, UUID):
                      try:
                          # Attempt to convert to UUID object
                          new_user_id = UUID(str(new_user_id))
                      except (ValueError, TypeError) as e:
                           logger.error(
                               f"DAL: Returned NewUserID is not a valid UUID: {new_user_id}. Error: {e}")
                           raise DALError(
                               f"User creation failed: Invalid User ID format returned: {new_user_id}") from e

                 logger.info(
                     f"DAL: User {username} created with NewUserID: {new_user_id}. Fetching full info.")

                 # 4. 获取完整用户信息 using the created ID
                 # This step is necessary to return the full UserResponseSchema as expected by the service/router
                 full_user_info = await self.get_user_by_id(conn, new_user_id)
                 logger.debug(
                     f"DAL: get_user_by_id for new user {new_user_id} returned: {full_user_info}")

                 if not full_user_info:
                     # This indicates a subsequent read failed right after creation
                     logger.error(
                         f"DAL: Failed to retrieve full user info after creation for ID: {new_user_id}")
                     raise DALError(
                         f"Failed to retrieve full user info after creation for ID: {new_user_id}")

                 logger.info(f"DAL: Full info retrieved for new user: {username}")
                 return full_user_info  # Return the fetched dictionary

            else:
                # If NewUserID is NOT present, check for explicit error messages or result codes.

                # 5. 检查错误消息或操作结果码
                error_message = result.get('Error') or result.get(
                    'Message') or result.get('')
                # Assuming SP might return this
                result_code = result.get('OperationResultCode')

                # Check for error messages from SP
                if error_message:
                    logger.debug(
                        f"DAL: sp_CreateUser for {username} returned message: {error_message}")
                    if '用户名已存在' in error_message or 'Duplicate username' in error_message:
                        logger.warning(f"DAL: Username {username} already exists")
                        raise IntegrityError("Username already exists.")
                    elif '手机号码已存在' in error_message or '手机号已存在' in error_message or 'Duplicate phone' in error_message:
                        logger.warning(
                            f"DAL: Phone number {phone_number} already exists")
                        raise IntegrityError("Phone number already exists.")
                    # Handle other potential SP-specific errors
                    logger.error(
                        f"DAL: Stored procedure error during user creation: {error_message}")
                    raise DALError(
                        f"Stored procedure error during user creation: {error_message}")

                # Check result code if available and no explicit error message
                if result_code is not None:
                     if result_code != 0:  # Assuming 0 is success
                          logger.error(
                              f"DAL: sp_CreateUser for {username} returned non-zero result code: {result_code}. Result: {result}")
                          # Map result code to specific error if possible, otherwise raise generic DALError
                          # Example: User already exists (though messages above should catch this)
                          if result_code == -1:
                               raise IntegrityError(
                                   "User already exists (code -1).")
                          else:
                               raise DALError(
                                   f"Stored procedure failed with result code: {result_code}")

            # 3. 检查是否包含 NewUserID (Assuming this is the primary success indicator from SP)
            new_user_id = result.get('NewUserID')
            if not new_user_id:
                # This could happen if SP executed without explicit error but didn't return the ID as expected
                logger.error(
                    f"DAL: sp_CreateUser for {username} completed but did not return NewUserID. Result: {result}")
                raise DALError(
                    "User creation failed: User ID not returned from database.")

            # 4. Validate NewUserID is a valid UUID string or UUID object
            if not isinstance(new_user_id, UUID):
                 try:
                     # Attempt to convert to UUID object
                     new_user_id = UUID(str(new_user_id))
                 except (ValueError, TypeError) as e:
                      logger.error(
                          f"DAL: Returned NewUserID is not a valid UUID: {new_user_id}. Error: {e}")
                      raise DALError(
                          f"User creation failed: Invalid User ID format returned: {new_user_id}") from e

            logger.info(
                f"DAL: User {username} created with NewUserID: {new_user_id}. Fetching full info.")

            # 5. 获取完整用户信息 using the created ID
            # This step is necessary to return the full UserResponseSchema as expected by the service/router
            full_user_info = await self.get_user_by_id(conn, new_user_id)
            logger.debug(
                f"DAL: get_user_by_id for new user {new_user_id} returned: {full_user_info}")

            if not full_user_info:
                # This indicates a subsequent read failed right after creation
                logger.error(
                    f"DAL: Failed to retrieve full user info after creation for ID: {new_user_id}")
                raise DALError(
                    f"Failed to retrieve full user info after creation for ID: {new_user_id}")

            logger.info(f"DAL: Full info retrieved for new user: {username}")
            return full_user_info  # Return the fetched dictionary

        except IntegrityError:
            raise  # Re-raise known integrity errors
        except DALError:
            raise  # Re-raise DAL errors originating from our checks
        except pyodbc.IntegrityError as e:
            # Catch pyodbc.IntegrityError raised by the driver for constraint violations
            logger.error(
                f"DAL: pyodbc.IntegrityError during user creation for {username}: {e}")
            error_message = str(e)
            # Check for specific error messages related to unique constraints
            error_message_lower = error_message.lower()
            if ('duplicate key' in error_message_lower or '违反唯一约束' in error_message_lower) and ('username' in error_message_lower or '用户名' in error_message_lower):
                raise IntegrityError("Username already exists.") from e
            elif ('duplicate key' in error_message_lower or '违反唯一约束' in error_message_lower) and ('phone' in error_message_lower or '手机' in error_message_lower):
                 raise IntegrityError("Phone number already exists.") from e
            else:
                logger.error(
                    f"DAL: Unexpected pyodbc.IntegrityError during user creation: {e}")
                raise DALError(
                    f"Database integrity error during user creation: {e}") from e
        except Exception as e:
            logger.error(f"DAL: Generic Error creating user {username}: {e}")
            # Catch any other unexpected exceptions during the DAL operation
            raise DALError(f"Database error during user creation: {e}") from e

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, *, major: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None, phone_number: Optional[str] = None) -> dict | None:
        """更新现有用户的个人资料，返回更新后的用户数据。"""
        logger.debug(
            # Add logging
            f"DAL: Attempting to update profile for user ID: {user_id}")
        sql = "{CALL sp_UpdateUserProfile(?, ?, ?, ?, ?)}"
        try:
            # Add logging
            logger.debug(
                f"DAL: Executing sp_UpdateUserProfile for ID {user_id}")
            # sp_UpdateUserProfile should return the updated user data (a dict) or indicate error/not found
            result = await self._execute_query(
                conn, sql,
                (user_id, major, avatar_url, bio, phone_number),
                fetchone=True
            )
            # Add logging
            logger.debug(
                f"DAL: sp_UpdateUserProfile for ID {user_id} returned: {result}")

            # Assuming SP returns the updated user data or a success indicator
            if result and isinstance(result, dict):
                error_message = result.get('') or result.get(
                    'Error') or result.get('Message')
                # Assuming SP might return this
                result_code = result.get('OperationResultCode')

                if error_message:
                    # Add logging
                    logger.warning(
                        f"DAL: sp_UpdateUserProfile for ID {user_id} returned error: {error_message}")
                    if '用户未找到' in error_message or 'User not found.' in error_message:
                        raise NotFoundError(
                            f"User with ID {user_id} not found for update.")
                    # Prioritize checking for specific duplicate phone error message from SP
                    elif '此手机号码已被其他用户使用' in error_message or '手机号码已存在' in error_message or 'Phone number already in use' in error_message or '手机号已存在' in error_message:
                         raise IntegrityError(
                             "Phone number already in use by another user.")
                    else:
                         # If it's an error from SP but not specific to user not found or duplicate phone
                         raise DALError(
                             f"Stored procedure error during profile update: {error_message}")

                if result_code is not None and result_code != 0:
                    logger.warning(
                        f"DAL: sp_UpdateUserProfile for ID {user_id} returned non-zero result code: {result_code}. Result: {result}")
                    # Handle specific result codes if necessary
                    raise DALError(
                        f"Stored procedure failed with result code: {result_code}")

                # If no error message and no non-zero result code, assume success and return the fetched data
                # Add logging
                logger.debug(
                    f"DAL: Profile update for ID {user_id} successful.")
                # Return the dictionary fetched by execute_query(fetchone=True) which should be the updated user data
                return result
            elif result is None:
                 # Add logging
                 logger.debug(
                     f"DAL: Profile update for ID {user_id} returned None.")
                 # If SP is designed to return None for user not found
                 raise NotFoundError(
                     f"User with ID {user_id} not found for update.")

            # If result is not None and not a dict with an error message, assume success and return the data
            # Add logging
            logger.warning(
                f"DAL: Profile update for ID {user_id} returned unexpected non-dict result: {result}")
            # Decide how to handle this - maybe raise an error or return None assuming failure
            raise DALError(
                f"Database error during profile update: Unexpected result format: {result}")

        except (NotFoundError, IntegrityError) as e:
             # Add logging
             logger.error(
                 f"DAL: Specific Error during profile update for ID {user_id}: {e}")
             raise e  # Re-raise specific errors caught from our checks
        except pyodbc.IntegrityError as e:
             # Catch pyodbc.IntegrityError raised by the driver
             # Add logging
             logger.error(
                 f"DAL: pyodbc.IntegrityError during profile update for ID {user_id}: {e}")
             error_message = str(e)
             # Check for specific error messages related to duplicate phone number from the driver
             # These might be different depending on the database and driver configuration
             error_message_lower = error_message.lower()
             # Example patterns for duplicate key errors, specifically looking for phone number context
             if ('duplicate key' in error_message_lower or '违反唯一约束' in error_message_lower) and ('phone' in error_message_lower or '手机' in error_message_lower):
                 raise IntegrityError(
                     "Phone number already in use by another user.") from e
             else:
                 # Re-raise other IntegrityErrors as DALError or a more specific error
                 logger.error(
                     f"DAL: Unexpected pyodbc.IntegrityError during profile update: {e}")
                 raise DALError(
                     f"Database integrity error during profile update: {e}") from e
        except Exception as e:
            # Add logging
            logger.error(
                f"DAL: Generic Error updating user profile for {user_id}: {e}")
            # Catch any other unexpected exceptions during the DAL operation
            raise DALError(
                f"Database error during user profile update: {e}") from e

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, hashed_password: str) -> bool:
        """更新用户密码。"""
        logger.debug(
            # Add logging
            f"DAL: Attempting to update password for user ID: {user_id}")
        sql = "{CALL sp_UpdateUserPassword(?, ?)}"
        try:
            # 调用 sp_UpdateUserPassword 存储过程
            # Use the injected execute_query function. SP returns a single row result.
            # Add logging
            logger.debug(
                f"DAL: Executing sp_UpdateUserPassword for ID {user_id}")
            result = await self._execute_query(conn, sql, (user_id, hashed_password), fetchone=True)
            # Add logging
            logger.debug(
                f"DAL: sp_UpdateUserPassword for ID {user_id} returned: {result}")

            if result and isinstance(result, dict):
                 error_message = result.get('') or result.get(
                     'Error') or result.get('Message')
                 result_code = result.get('OperationResultCode')

                 if error_message:
                     # Add logging
                     logger.warning(
                         f"DAL: Password update failed for ID {user_id}: SP returned error: {error_message}")
                     if '用户不存在。' in error_message or 'User not found.' in error_message:
                          raise NotFoundError(
                              f"User with ID {user_id} not found for password update.")
                     if '密码更新失败。' in error_message or 'Password update failed.' in error_message:
                          # This indicates an internal SP logic error, not user input
                          raise DALError(
                              "Password update failed in stored procedure.")
                     raise DALError(
                         f"Stored procedure error during password update: {error_message}")

                 if result_code is not None and result_code != 0:
                      logger.warning(
                          f"DAL: sp_UpdateUserPassword for ID {user_id} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(
                          f"Stored procedure failed with result code: {result_code}")

                 # Assuming success if no error message and result_code is 0 or None
                 if '密码更新成功' in result.values() or 'Password updated successfully' in result.values():
                      # Add logging
                      logger.info(
                          f"DAL: Password updated successfully for user ID: {user_id}")
                      return True
                 else:
                     logger.warning(
                         f"DAL: sp_UpdateUserPassword for ID {user_id} returned ambiguous success indicator: {result}")
                     # If SP returns data but no clear success message, check if any row was affected?
                     # Or rely purely on exceptions. Let's assume SP should return a clear indicator.
                     # For now, if it's a dict and no error, assume success.
                     return True  # Assume success if no explicit error

            # If result is None or not a dict
            # Add logging
            logger.warning(
                f"DAL: sp_UpdateUserPassword for ID {user_id} returned unexpected result: {result}")
            # If user was not found, NotFoundError should have been raised by message check.
            # If update truly failed without an SP error message, return False or raise a generic DAL error.
            # Raising DALError is generally better for unexpected DB issues.
            raise DALError(
                f"Database error during user password update: Unexpected result: {result}")

        except NotFoundError:
             raise  # Re-raise NotFoundError
        except DALError:
             raise  # Re-raise DAL errors
        except Exception as e:
            # Add logging
            logger.error(
                f"DAL: Generic Error updating user password for user {user_id}: {e}")
            raise DALError(
                f"Database error during user password update: {e}") from e

    # New method: Get user password hash by ID
    async def get_user_password_hash_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> str | None:
        """根据用户 ID 获取密码哈希。"""
        logger.debug(
            # Add logging
            f"DAL: Attempting to get password hash for user ID: {user_id}")
        sql = "{CALL sp_GetUserPasswordHashById(?)}"
        try:
            # Use the injected execute_query function
            # Add logging
            logger.debug(
                f"DAL: Executing sp_GetUserPasswordHashById for ID {user_id}")
            # SP returns a single row with the Password hash or an error message
            result = await self._execute_query(conn, sql, (user_id,), fetchone=True)
            # Add logging
            logger.debug(
                f"DAL: sp_GetUserPasswordHashById for ID {user_id} returned: {result}")

            if result and isinstance(result, dict):
                error_message = result.get('') or result.get(
                    'Error') or result.get('Message')

                if error_message:
                     # Add logging
                     logger.debug(
                         f"DAL: Password hash not found for ID {user_id}: SP returned message: {error_message}")
                     # If message indicates user not found specifically
                     if '用户不存在。' in error_message or 'User not found.' in error_message:
                          return None  # User not found
                     # Handle other potential errors from SP
                     raise DALError(
                         f"Stored procedure error fetching password hash: {error_message}")

                if 'Password' in result:
                    # Add logging
                    logger.debug(f"DAL: Password hash found for ID {user_id}.")
                    return result['Password']

                # If result is a dict but doesn't contain 'Password' and no error message, unexpected
                # Add logging
                logger.warning(
                    f"DAL: sp_GetUserPasswordHashById for ID {user_id} returned dict without 'Password' key or error: {result}")
                # Treat as not found or DAL error? Let's return None assuming hash wasn't found as expected
                return None

            # If result is None or not a dict
            # Add logging
            logger.warning(
                f"DAL: sp_GetUserPasswordHashById for ID {user_id} returned unexpected result: {result}")
            return None  # Assume hash not found due to unexpected result

        except DALError:
             raise  # Re-raise DAL errors
        except Exception as e:
            # Add logging
            logger.error(
                f"DAL: Generic Error getting password hash for user ID {user_id}: {e}")
            raise DALError(
                f"Database error while fetching password hash: {e}") from e

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """Deletes a user by their ID using sp_DeleteUser, processing a single combined debug and result code output."""
        logger.info(f"DAL: Attempting to delete user with ID: {user_id}")

        result_data = None

        try:
            cursor = conn.cursor()
            logger.debug(f"DAL: Executing sp_DeleteUser for ID: {user_id}")
            cursor.execute("{CALL sp_DeleteUser(?)}", user_id)

            logger.debug(
                "DAL: Attempting to fetch the single result set from sp_DeleteUser.")
            # Using fetchone here assuming SP always returns exactly one row with result codes/messages
            row = cursor.fetchone()  # Use fetchone
            if row:
                # Construct a dictionary from the row object for easier access
                if cursor.description:
                    result_data = {column[0]: row[i] for i, column in enumerate(
                        cursor.description)}  # Access row by index
                    logger.info(
                        f"SP_DeleteUser Combined Output: {result_data}")
                else:
                    logger.warning(
                        f"SP_DeleteUser: cursor.description not available for the result set. Raw row: {row}")
                    # Fallback or error handling if column names are unknown
                    # This makes accessing OperationResultCode unreliable.
                    # We MUST rely on the structure defined by the SP's SELECT statement.
                    # If the first few columns are debug info and the last is ResultCode,
                    # we could try accessing by index, but column names are safer.
                    # Let's assume cursor.description works or the keys are in the fetched dict if fetchone returns a dict.
                    # If fetchone returns a pyodbc.Row, we need description.
                    pass  # Keep result_data as None if description fails

            else:
                logger.warning(
                    "SP_DeleteUser did not return the expected result set (fetchone returned None).")

            cursor.close()

            # Access OperationResultCode from the constructed dictionary
            operation_result_code = result_data.get(
                'OperationResultCode') if result_data and isinstance(result_data, dict) else None
            debug_message = result_data.get('Debug_Message') if result_data and isinstance(
                result_data, dict) else "No debug message available."

            if operation_result_code == 0:
                # conn.commit() # Commit handled by execute_query implicitly if commit=True
                logger.info(
                    f"DAL: User {user_id} deleted successfully (OperationResultCode: 0).")
                return True
            elif operation_result_code == -1:
                logger.warning(
                    f"DAL: User {user_id} not found by sp_DeleteUser (OperationResultCode: -1). Debug: {debug_message}")
                # conn.rollback() # Rollback handled by execute_query implicitly on error/non-commit
                raise NotFoundError(
                    f"User with ID {user_id} not found for deletion.")
            elif operation_result_code == -2:
                logger.warning(
                    f"DAL: User {user_id} could not be deleted due to dependencies (OperationResultCode: -2). Debug: {debug_message}")
                # conn.rollback()
                # Raise a specific error for dependencies, or a generic Forbidden/DAL error
                raise ForbiddenError(
                    f"Cannot delete user with ID {user_id} due to existing dependencies.")
            elif operation_result_code == -3:
                logger.warning(
                    f"DAL: User {user_id} was found but DELETE operation failed (OperationResultCode: -3). Debug: {debug_message}")
                # conn.rollback()
                raise DALError(
                    f"Database failed to delete user with ID {user_id} (code -3).")
            elif operation_result_code == -4:
                logger.warning(
                    f"DAL: Database error during sp_DeleteUser's transaction (OperationResultCode: -4). Debug: {debug_message}")
                # conn.rollback()
                raise DALError(
                    f"Database transaction error during user deletion for ID {user_id} (code -4).")
            elif operation_result_code == -90:
                logger.warning(
                    f"DAL: Database error during sp_DeleteUser's initial user check (OperationResultCode: -90). Debug: {debug_message}")
                # conn.rollback()
                raise DALError(
                    f"Database error during initial user check for ID {user_id} (code -90).")
            elif operation_result_code is None:
                 # Handle case where OperationResultCode was not found in the result
                 logger.error(
                     f"DAL: sp_DeleteUser for user {user_id} returned result data but no OperationResultCode. Result: {result_data}")
                 # conn.rollback()
                 raise DALError(
                     f"Database error during user deletion: Missing result code. Result: {result_data}")
            else:
                logger.warning(
                    f"DAL: sp_DeleteUser for user {user_id} returned an unexpected OperationResultCode: {operation_result_code}. Debug: {debug_message}. Rolling back.")
                # conn.rollback()
                raise DALError(
                    f"Database error during user deletion: Unexpected result code {operation_result_code}. Debug: {debug_message}")

        except (NotFoundError, ForbiddenError, DALError) as e:
             # Catch and re-raise specific exceptions raised above
             logger.error(
                 f"DAL: Specific error during user deletion for {user_id}: {e}")
             # Rollback is handled by execute_query implicitly on exception
             raise e
        except pyodbc.Error as e:
            logger.error(
                f"DAL: Database error during user deletion for {user_id}: {e}")
            # Rollback is handled by execute_query implicitly on exception
            raise DALError(f"Database error during user deletion: {e}") from e
        except Exception as ex:
            logger.error(
                f"DAL: Unexpected Python error during user deletion for {user_id}: {ex}")
            # Rollback is handled by execute_query implicitly on exception
            raise DALError(
                f"Unexpected server error during user deletion: {ex}") from ex
        # No finally block needed for cursor close if using execute_query as it manages cursor.

    async def request_verification_link(self, conn: pyodbc.Connection, user_id: Optional[UUID] = None, email: Optional[str] = None) -> dict:
         """
         请求邮箱验证链接，调用sp_RequestMagicLink。
         可以根据 user_id 或 email 请求。用于用户已登录请求验证，或未登录通过邮箱请求。
         当用户已登录 (@user_id is not null) 并提供 @email 时，存储过程应更新用户的 Email 字段。
         """
         logger.debug(
             f"DAL: Requesting verification link for user_id: {user_id}, email: {email}")
         # Assuming sp_RequestMagicLink now takes @userId (optional) and @email (required)
         sql = "{CALL sp_RequestMagicLink(?, ?)}" # New SP signature
         params = (email, user_id) # Correct the order to match SP definition (@email, @userId)

         logger.debug(f"Calling stored procedure: {sql} with params: {params}")
         result = await self._execute_query(conn, sql, params, fetchone=True)

         # The DAL should handle cases like disabled account, email already verified etc.
         # If result indicates success (e.g., a token was generated/sent), return a success message.

         if result and isinstance(result, dict):
             error_message = result.get('') or result.get('Error') or result.get('Message')
             result_code = result.get('OperationResultCode')

             if error_message:
                 logger.warning(f"DAL: sp_RequestMagicLink failed for email {email}: SP returned error: {error_message}")
                 if '您的账户已被禁用，无法登录。' in error_message or 'Account is disabled.' in error_message:
                      # Or a more specific error
                      raise ForbiddenError("Account is disabled.")
                 if '邮件已存在' in error_message or 'Email already exists' in error_message:
                       # This case is handled by the SP creating a new user or updating existing.
                       # If it explicitly says email exists for *another* user and cannot be used?
                       # The existing SP doesn't seem to have this specific check.
                       # Rely on the SP's intended behavior for existing emails.
                       pass  # Do not raise error for email existing if SP handled it gracefully

             if result_code is not None and result_code != 0:
                 logger.warning(f"DAL: sp_RequestMagicLink for email {email} returned non-zero result code: {result_code}. Result: {result}")
                 raise DALError(f"Stored procedure failed with result code: {result_code}")

             # Stored procedure returns VerificationToken, UserID, IsNewUser on success
             if all(key in result for key in ['VerificationToken', 'UserID', 'IsNewUser']):
                 logger.info(f"DAL: Magic link requested successfully for email {email}.")
                 return result # Return the dictionary

             # If result is a dict but doesn't contain expected keys and no error message
             logger.warning(f"DAL: sp_RequestMagicLink for email {email} returned unexpected dict format: {result}")
             raise DALError("Request verification link failed: Unexpected response format from stored procedure.")

         # If result is None or not a dict
         logger.error(f"DAL: sp_RequestMagicLink for email {email} returned unexpected result: {result}")
         raise DALError("Request verification link failed: Unexpected database response.")

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
         """验证邮箱，调用sp_VerifyMagicLink。"""
         logger.debug(f"DAL: Verifying email with token: {token}")
         sql = "{CALL sp_VerifyMagicLink(?)}"
         try:
             # Use the injected execute_query function
             # sp_VerifyMagicLink returns UserID, IsVerified, and potentially error messages.
             result = await self._execute_query(conn, sql, (token,), fetchone=True)

             logger.debug(f"DAL: sp_VerifyMagicLink with token {token} returned: {result}")

             if result and isinstance(result, dict):
                 error_message = result.get('') or result.get('Error') or result.get('Message')
                 result_code = result.get('OperationResultCode')

                 if error_message:
                     logger.warning(f"DAL: sp_VerifyMagicLink failed for token {token}: SP returned error: {error_message}")
                     if '魔术链接无效或已过期。' in error_message or 'Magic link invalid or expired.' in error_message:
                          raise DALError("验证链接无效或已过期，请重新申请。") # Specific user-friendly message
                     if '您的账户已被禁用，无法登录。' in error_message or 'Account is disabled.' in error_message:
                          raise ForbiddenError("账户已被禁用。") # Specific user-friendly message

                     raise DALError(f"Stored procedure error verifying email: {error_message}")

                 if result_code is not None and result_code != 0:
                      logger.warning(f"DAL: sp_VerifyMagicLink for token {token} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(f"Stored procedure failed with result code: {result_code}")


                 # Stored procedure returns UserID, IsVerified on success
                 if all(key in result for key in ['UserID', 'IsVerified']):
                      logger.info(f"DAL: Magic link verified successfully for token {token}.")
                      return result # Return the dictionary

                 # If result is a dict but doesn't contain expected keys and no error message
                 logger.warning(f"DAL: sp_VerifyMagicLink for token {token} returned unexpected dict format: {result}")
                 raise DALError("Verify email failed: Unexpected response format from stored procedure.")

             # If result is None or not a dict
             logger.error(f"DAL: sp_VerifyMagicLink for token {token} returned unexpected result: {result}")
             raise DALError("Verify email failed: Unexpected database response.")


         except (ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
         except Exception as e:
             logger.error(f"Error verifying email with token {token}: {e}")
             raise DALError(f"Database error during email verification: {e}") from e

    async def get_system_notifications_by_user_id(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """获取某个用户的系统通知列表。"""
        logger.debug(f"DAL: Getting system notifications for user {user_id}.")
        sql = "{CALL sp_GetSystemNotificationsByUserId(?)}"
        try:
            # Use the injected execute_query function
            result = await self._execute_query(conn, sql, (user_id,), fetchall=True)
            logger.debug(f"DAL: sp_GetSystemNotificationsByUserId for user {user_id} returned: {result}")

            if result and isinstance(result, list):
                 # Check if the list contains an error message indicator from SP
                 if any(isinstance(row, dict) and ('用户不存在。' in row.values() or 'User not found.' in row.values()) for row in result):
                      logger.debug(f"DAL: User {user_id} not found according to SP, no notifications returned.")
                      return [] # User not found or no notifications
                 # Assuming a list of dicts is the expected notification data
                 # Map keys if necessary (though SP columns seem mapped in Service)
                 return result
            elif result is None:
                 logger.debug(f"DAL: sp_GetSystemNotificationsByUserId for user {user_id} returned None.")
                 return [] # No users or no notifications
            else:
                 logger.warning(f"DAL: sp_GetSystemNotificationsByUserId for user {user_id} returned unexpected result type: {result}")
                 # Decide how to handle unexpected types - empty list or raise error
                 raise DALError("Database error while fetching system notifications: Unexpected data format.")

        except DALError:
             raise # Re-raise DAL errors
        except Exception as e:
            logger.error(f"Error getting system notifications for user {user_id}: {e}")
            raise DALError(f"Database error while fetching system notifications: {e}") from e

    async def mark_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """标记系统通知为已读。"""
        logger.debug(f"DAL: Marking notification {notification_id} as read for user {user_id}")
        sql = "{CALL sp_MarkNotificationAsRead(?, ?)}"
        try:
            # Use the injected execute_query function. SP returns a single row result.
            result = await self._execute_query(conn, sql, (notification_id, user_id), fetchone=True)
            logger.debug(f"DAL: sp_MarkNotificationAsRead for notification {notification_id}, user {user_id} returned: {result}")

            if result and isinstance(result, dict):
                error_message = result.get('') or result.get('Error') or result.get('Message')
                result_code = result.get('OperationResultCode')

                if error_message:
                     logger.warning(f"DAL: Mark notification as read failed: SP returned error: {error_message}")
                     if '通知不存在。' in error_message or 'Notification not found.' in error_message:
                          raise NotFoundError(f"Notification with ID {notification_id} not found.")
                     if '无权标记此通知为已读。' in error_message or 'No permission to mark this notification as read.' in error_message:
                          raise ForbiddenError(f"User {user_id} does not have permission to mark notification {notification_id} as read.")
                     raise DALError(f"Stored procedure error marking notification as read: {error_message}")

                if result_code is not None and result_code != 0:
                      logger.warning(f"DAL: sp_MarkNotificationAsRead for notif {notification_id}, user {user_id} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(f"Stored procedure failed with result code: {result_code}")


                if '通知标记为已读成功。' in result.values() or 'Notification marked as read successfully.' in result.values():
                     logger.info(f"DAL: Notification {notification_id} marked as read for user {user_id}")
                     return True
                else:
                     logger.warning(f"DAL: sp_MarkNotificationAsRead for notif {notification_id}, user {user_id} returned ambiguous success indicator: {result}")
                     # Assume success if no error and result is a dict
                     return True

            # If result is None or not a dict
            logger.warning(f"DAL: sp_MarkNotificationAsRead for notif {notification_id}, user {user_id} returned unexpected result: {result}")
            # If not found/forbidden, an exception should have been raised by message check.
            # If update truly failed without an SP error message, return False or raise DAL error.
            raise DALError(f"Database error while marking notification as read: Unexpected result: {result}")

        except (NotFoundError, ForbiddenError, DALError) as e:
            raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error marking notification {notification_id} as read for user {user_id}: {e}")
            raise DALError(f"Database error while marking notification as read: {e}") from e

    async def set_chat_message_visibility(self, conn: pyodbc.Connection, message_id: UUID, user_id: UUID, visible_to: str, is_visible: bool) -> bool:
        """设置聊天消息对发送者或接收者的可见性（逻辑删除）。"""
        logger.debug(f"DAL: Setting chat message {message_id} visibility for user {user_id}.")
        sql = "{CALL sp_SetChatMessageVisibility(?, ?, ?, ?)}"
        try:
            # Use the injected execute_query function. SP returns a single row result.
            result = await self._execute_query(conn, sql, (message_id, user_id, visible_to, is_visible), fetchone=True)
            logger.debug(f"DAL: sp_SetChatMessageVisibility for message {message_id}, user {user_id} returned: {result}")

            if result and isinstance(result, dict):
                 error_message = result.get('') or result.get('Error') or result.get('Message')
                 result_code = result.get('OperationResultCode')

                 if error_message:
                     logger.warning(f"DAL: Set message visibility failed: SP returned error: {error_message}")
                     if '消息不存在。' in error_message or 'Message not found.' in error_message:
                          raise NotFoundError(f"Message with ID {message_id} not found.")
                     if '无权修改此消息的可见性。' in error_message or 'No permission to modify this message visibility.' in error_message:
                          raise ForbiddenError(f"User {user_id} does not have permission to modify visibility of message {message_id}.")
                     raise DALError(f"Stored procedure error setting message visibility: {error_message}")

                 if result_code is not None and result_code != 0:
                      logger.warning(f"DAL: sp_SetChatMessageVisibility for msg {message_id}, user {user_id} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(f"Stored procedure failed with result code: {result_code}")


                 if '消息可见性设置成功' in result.values() or 'Message visibility set successfully' in result.values():
                      logger.info(f"DAL: Message {message_id} visibility set successfully for user {user_id}.")
                      return True
                 else:
                      logger.warning(f"DAL: sp_SetChatMessageVisibility for msg {message_id}, user {user_id} returned ambiguous success indicator: {result}")
                      return True

            # If result is None or not a dict
            logger.warning(f"DAL: sp_SetChatMessageVisibility for msg {message_id}, user {user_id} returned unexpected result: {result}")
            raise DALError(f"Database error while setting message visibility: Unexpected result: {result}")


        except (NotFoundError, ForbiddenError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error setting message visibility for message {message_id}, user {user_id}: {e}")
            raise DALError(f"Database error while setting message visibility: {e}") from e

    # New admin methods for user management
    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """管理员禁用/启用用户账户。"""
        logger.debug(f"DAL: Admin {admin_id} attempting to change status of user {user_id} to {new_status}")
        sql = "{CALL sp_ChangeUserStatus(?, ?, ?)}"
        try:
            # Use the injected execute_query function. SP returns a single row result.
            result = await self._execute_query(conn, sql, (user_id, new_status, admin_id), fetchone=True)
            logger.debug(f"DAL: sp_ChangeUserStatus for user {user_id}, admin {admin_id} returned: {result}")

            if result and isinstance(result, dict):
                 error_message = result.get('') or result.get('Error') or result.get('Message')
                 result_code = result.get('OperationResultCode')

                 if error_message:
                     logger.warning(f"DAL: Change user status failed: SP returned error: {error_message}")
                     if '用户不存在。' in error_message or 'User not found.' in error_message:
                          raise NotFoundError(f"User with ID {user_id} not found.")
                     if '无权限执行此操作' in error_message or 'Only administrators can change user status.' in error_message:
                          raise ForbiddenError("只有管理员可以更改用户状态。")
                     if '无效的用户状态' in error_message or 'Invalid user status.' in error_message:
                          raise ValueError("无效的用户状态，状态必须是 Active 或 Disabled。") # Use ValueError for bad input value

                     raise DALError(f"Stored procedure error changing user status: {error_message}")

                 if result_code is not None and result_code != 0:
                      logger.warning(f"DAL: sp_ChangeUserStatus for user {user_id}, admin {admin_id} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(f"Stored procedure failed with result code: {result_code}")

                 if '用户状态更新成功。' in result.values() or 'User status updated successfully.' in result.values():
                      logger.info(f"DAL: User {user_id} status changed to {new_status} by admin {admin_id}")
                      return True
                 else:
                      logger.warning(f"DAL: sp_ChangeUserStatus for user {user_id}, admin {admin_id} returned ambiguous success indicator: {result}")
                      return True

            # If result is None or not a dict
            logger.warning(f"DAL: sp_ChangeUserStatus for user {user_id}, admin {admin_id} returned unexpected result: {result}")
            raise DALError(f"Database error while changing user status: Unexpected result: {result}")


        except (NotFoundError, ForbiddenError, ValueError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error changing user status for user {user_id}, admin {admin_id}: {e}")
            raise DALError(f"Database error while changing user status: {e}") from e

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """管理员手动调整用户信用分。"""
        logger.debug(f"DAL: Admin {admin_id} attempting to adjust credit for user {user_id} by {credit_adjustment} with reason: {reason}")
        sql = "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}"
        try:
            # Use the injected execute_query function. SP returns a single row result.
            result = await self._execute_query(conn, sql, (user_id, credit_adjustment, admin_id, reason), fetchone=True)
            logger.debug(f"DAL: sp_AdjustUserCredit for user {user_id}, admin {admin_id} returned: {result}")

            if result and isinstance(result, dict):
                 error_message = result.get('') or result.get('Error') or result.get('Message')
                 result_code = result.get('OperationResultCode')

                 if error_message:
                      logger.warning(f"DAL: Adjust user credit failed: SP returned error: {error_message}")
                      if '用户不存在。' in error_message or 'User not found.' in error_message:
                           raise NotFoundError(f"User with ID {user_id} not found.")
                      if '无权限执行此操作' in error_message or 'Only administrators can adjust user credit.' in error_message:
                           raise ForbiddenError("只有管理员可以调整用户信用分。")
                      if '调整信用分必须提供原因。' in error_message or 'Reason for credit adjustment must be provided.' in error_message:
                           raise ValueError("调整信用分必须提供原因。") # Use ValueError

                      raise DALError(f"Stored procedure error adjusting user credit: {error_message}")

                 if result_code is not None and result_code != 0:
                      logger.warning(f"DAL: sp_AdjustUserCredit for user {user_id}, admin {admin_id} returned non-zero result code: {result_code}. Result: {result}")
                      raise DALError(f"Stored procedure failed with result code: {result_code}")


                 if '用户信用分调整成功。' in result.values() or 'User credit adjusted successfully.' in result.values():
                      logger.info(f"DAL: User {user_id} credit adjusted by {credit_adjustment} by admin {admin_id}")
                      return True
                 else:
                      logger.warning(f"DAL: sp_AdjustUserCredit for user {user_id}, admin {admin_id} returned ambiguous success indicator: {result}")
                      return True

            # If result is None or not a dict
            logger.warning(f"DAL: sp_AdjustUserCredit for user {user_id}, admin {admin_id} returned unexpected result: {result}")
            raise DALError(f"Database error while adjusting user credit: Unexpected result: {result}")


        except (NotFoundError, ForbiddenError, ValueError, DALError) as e:
             raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"DAL: Error adjusting user credit for user {user_id}, admin {admin_id}: {e}")
            raise DALError(f"Database error while adjusting user credit: {e}") from e

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[dict]:
        """管理员获取所有用户列表。"""
        logger.debug(f"DAL: Admin {admin_id} getting all users.")
        sql = "{CALL sp_GetAllUsers(?)}"
        try:
            # 调用 sp_GetAllUsers 存储过程. SP returns multiple rows (a list of dicts).
            result = await self._execute_query(conn, sql, (admin_id,), fetchall=True)
            logger.debug(f"DAL: sp_GetAllUsers for admin {admin_id} returned {len(result) if isinstance(result, list) else 'unexpected'} users.")

            if result is None:
                 logger.debug(f"DAL: sp_GetAllUsers for admin {admin_id} returned None.")
                 return [] # No users found or unexpected empty result

            if not isinstance(result, list):
                 # Handle unexpected result format (e.g., error message returned as single dict)
                 if isinstance(result, dict):
                      error_message = result.get('') or result.get('Error') or result.get('Message')
                      if error_message:
                           logger.warning(f"DAL: sp_GetAllUsers failed for admin {admin_id}: SP returned error: {error_message}")
                           if "无权限执行此操作" in error_message or "Only administrators can view all users" in error_message:
                                raise ForbiddenError(error_message) # 将数据库权限错误转换为应用层异常
                           if "管理员不存在" in error_message or "Admin user not found" in error_message:
                                raise NotFoundError(error_message) # 管理员不存在也算一种"无权限"
                           raise DALError(f"Stored procedure error fetching all users: {error_message}")

                 logger.error(f"DAL: Unexpected result format from sp_GetAllUsers for admin {admin_id}: {result}")
                 raise DALError("Database error while fetching all users: Unexpected data format.")

            # Assuming result is a list of dictionaries
            # Map keys if necessary (though SP columns seem mapped in Service)
            return result # Returns a list of user dictionaries

        except (ForbiddenError, NotFoundError, DALError) as e:
            raise e # Re-raise specific exceptions
        except Exception as e:
            # Catch any exception during query execution, including those from RAISERROR
            logger.error(f"DAL: Generic Error getting all users for admin {admin_id}: {e}")
            raise DALError(f"Database error while fetching all users: {e}") from e 