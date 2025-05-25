# app/services/user_service.py
import pyodbc
from uuid import UUID
from typing import Optional
import logging

logger = logging.getLogger(__name__) # Initialize logger

from app.dal.user_dal import UserDAL # Import the UserDAL class
from app.schemas.user_schemas import UserRegisterSchema, UserLoginSchema, UserProfileUpdateSchema, UserPasswordUpdate, UserStatusUpdateSchema, UserCreditAdjustmentSchema, UserResponseSchema # Import necessary schemas
from app.utils.auth import get_password_hash, verify_password, create_access_token # Importing auth utilities
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions
from datetime import timedelta # Needed for token expiry
from app.config import settings # Import settings object
from datetime import datetime # Import datetime for data conversion

# Removed direct instantiation of DAL
# user_dal = UserDAL()

# Encapsulate Service functions within a class
class UserService:
    def __init__(self, user_dal: UserDAL):
        self.user_dal = user_dal

    async def create_user(self, conn: pyodbc.Connection, user_data: UserRegisterSchema) -> UserResponseSchema:
        """创建新用户。

        Args:
            conn: 数据库连接对象。
            user_data: 用户注册数据 Pydantic Schema。

        Returns:
            新创建用户的 UserResponseSchema。

        Raises:
            IntegrityError: 如果用户名或手机号已存在。
            DALError: 如果发生其他数据库错误。
        """
        logger.info(f"Attempting to create user: {user_data.username}") # Add logging

        hashed_password = get_password_hash(user_data.password)
        logger.debug(f"Password hashed for {user_data.username}") # Add logging

        try:
            # Call DAL to create user
            logger.debug(f"Calling DAL.create_user for {user_data.username}") # Add logging
            created_user = await self.user_dal.create_user(
                conn,
                user_data.username,
                hashed_password,
                user_data.phone_number,
                major=user_data.major
            )
            logger.debug(f"DAL.create_user returned: {created_user}") # Add logging

            # After successful creation in DAL, fetch the complete user profile
            # This is needed to populate all fields for UserResponseSchema, including default values etc.
            # Assuming DAL.create_user returns the dictionary representation of the created user.
            # If DAL.create_user only returns ID, we would need get_user_profile_by_id here.

            # Convert the DAL dictionary result to a dictionary matching UserResponseSchema keys
            logger.debug(f"Converting DAL user data to schema for {user_data.username}") # Add logging
            converted_user_data = self._convert_dal_user_to_schema(created_user) # Convert DAL dict to schema dict
            logger.debug(f"Converted user data: {converted_user_data}") # Add logging

            logger.info(f"User created successfully: {user_data.username}") # Add logging
            return converted_user_data # Return the converted dict

        except (IntegrityError, NotFoundError) as e:
            # Re-raise specific exceptions from DAL
            logger.error(f"IntegrityError or NotFoundError during user creation for {user_data.username}: {e}") # Add logging
            raise e
        except DALError as e:
            # Wrap general DAL errors in a Service layer error with more context
            logger.error(f"Database error during user creation for {user_data.username}: {e}") # Add logging
            raise DALError(f"Database error during user creation: {e}") from e # Wrap and re-raise
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error during user creation for {user_data.username}: {e}") # Add logging
            raise e # Re-raise other unexpected errors

    async def authenticate_user_and_create_token(self, conn: pyodbc.Connection, username: str, password: str) -> str:
        """
        Service layer function to authenticate a user and generate a JWT token.
        Calls DAL to get user, verifies password, checks status, and creates token.
        """
        logger.info(f"Attempting to authenticate user: {username}") # Add logging

        # 1. Call DAL to get user with password hash
        logger.debug(f"Calling DAL.get_user_by_username_with_password for {username}") # Add logging
        user = await self.user_dal.get_user_by_username_with_password(conn, username)
        logger.debug(f"DAL.get_user_by_username_with_password returned: {user}") # Add logging

        if not user:
            # User not found
            logger.warning(f"Authentication failed: User {username} not found.") # Add logging
            raise AuthenticationError("用户名或密码不正确")

        # 2. Verify password
        stored_password_hash = user.get('Password')
        logger.debug(f"Verifying password for user: {username}") # Add logging
        if not stored_password_hash or not verify_password(password, stored_password_hash):
            # Password doesn't match
            logger.warning(f"Authentication failed: Incorrect password for user {username}.") # Add logging
            raise AuthenticationError("用户名或密码不正确")

        # 3. Check user status (e.g., Disabled) - Business logic in Service
        logger.debug(f"Checking status for user: {username} (Status: {user.get('Status')})") # Add logging
        if user.get('Status') == 'Disabled':
            logger.warning(f"Authentication failed: Account for user {username} is disabled.") # Add logging
            raise ForbiddenError("账户已被禁用") # Raise a specific exception

        # TODO: Check if user is verified if verification is required for login
        # if not user.get('IsVerified') and require_verification:
        #     raise ForbiddenError("邮箱未验证，请先验证邮箱")

        # 4. Create JWT Token
        logger.debug(f"Creating JWT token for user: {username}") # Add logging
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Use user data (like UserID, IsStaff) to create the token payload
        # Ensure UserID is correctly accessed from the user dict returned by DAL
        user_id = user.get('UserID') # Assuming DAL returns 'UserID'
        is_staff = user.get('IsStaff', False) # Assuming DAL returns 'IsStaff'
        is_verified = user.get('IsVerified', False) # Assuming DAL returns 'IsVerified'

        if not user_id:
             # This should not happen if DAL works correctly
             logger.error(f"DAL error: UserID missing for {username} after fetching.") # Add logging
             raise DALError("Failed to retrieve UserID for token creation after authentication.")

        access_token = create_access_token(
            data={
                "user_id": str(user_id), # Ensure user_id is string in token
                "is_staff": is_staff,
                "is_verified": is_verified # Include verification status in token
            },
            expires_delta=access_token_expires
        )
        logger.info(f"Authentication successful, token created for user: {username}") # Add logging
        return access_token # Return the token string

    async def get_user_profile_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> UserResponseSchema:
        """
        Service layer function to get user profile by ID.
        Handles NotFoundError from DAL.
        """
        logger.info(f"Attempting to get user profile by ID: {user_id}") # Add logging
        # Pass the connection to the DAL method
        user = await self.user_dal.get_user_by_id(conn, user_id)
        logger.debug(f"DAL.get_user_by_id returned: {user}") # Add logging
        if not user:
            logger.warning(f"User profile not found for ID: {user_id}") # Add logging
            raise NotFoundError(f"User with ID {user_id} not found.")
        
        # Convert DAL response keys to match UserResponseSchema
        logger.debug(f"Converting DAL user data to schema for ID: {user_id}") # Add logging
        return self._convert_dal_user_to_schema(user) # Return the converted dict

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, user_update_data: UserProfileUpdateSchema) -> UserResponseSchema:
        """
        Service layer function to update user profile.
        """
        logger.info(f"Attempting to update profile for user ID: {user_id}")
        # Filter out None values from the update data to avoid unnecessary updates
        update_data = user_update_data.model_dump(exclude_none=True)

        if not update_data:
            logger.info(f"No update data provided for user ID: {user_id}")
            # If no data to update, just return the current profile
            return await self.get_user_profile_by_id(conn, user_id)

        try:
            logger.debug(f"Calling DAL.update_user_profile for user ID: {user_id} with data: {update_data}")
            updated_dal_user = await self.user_dal.update_user_profile(conn, user_id, **update_data)
            logger.debug(f"DAL.update_user_profile returned: {updated_dal_user}")

            if not updated_dal_user:
                 # This could happen if the user_id was not found in DAL update
                 logger.warning(f"User not found during profile update for ID: {user_id}")
                 raise NotFoundError(f"User with ID {user_id} not found for update.")
            
            logger.debug(f"Converting updated DAL user data to schema for user ID: {user_id}")
            return self._convert_dal_user_to_schema(updated_dal_user)

        except (IntegrityError, NotFoundError) as e:
            logger.error(f"IntegrityError or NotFoundError during profile update for user ID {user_id}: {e}")
            raise e
        except DALError as e:
            logger.error(f"Database error during profile update for user ID {user_id}: {e}")
            raise DALError(f"Database error during profile update: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during profile update for user ID {user_id}: {e}")
            raise e

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, password_update_data: UserPasswordUpdate) -> bool:
        """
        Service layer function to update user password.
        Verifies old password and updates with new hashed password.
        """
        logger.info(f"Attempting to update password for user ID: {user_id}")
        
        # 1. Get current password hash from DAL
        logger.debug(f"Calling DAL.get_user_password_hash_by_id for user ID: {user_id}")
        stored_password_hash = await self.user_dal.get_user_password_hash_by_id(conn, user_id)
        logger.debug(f"DAL.get_user_password_hash_by_id returned hash: {stored_password_hash}")

        if not stored_password_hash:
            logger.warning(f"User not found during password update for ID: {user_id}")
            raise NotFoundError(f"User with ID {user_id} not found.")

        # 2. Verify old password
        logger.debug(f"Verifying old password for user ID: {user_id}")
        if not verify_password(password_update_data.old_password, stored_password_hash):
            logger.warning(f"Password update failed: Incorrect old password for user ID {user_id}.") # Add logging
            raise AuthenticationError("旧密码不正确") # Use AuthenticationError for incorrect password

        # 3. Hash new password
        new_hashed_password = get_password_hash(password_update_data.new_password)
        logger.debug(f"New password hashed for user ID: {user_id}")

        # 4. Update password in DAL
        logger.debug(f"Calling DAL.update_user_password for user ID: {user_id}")
        update_success = await self.user_dal.update_user_password(conn, user_id, new_hashed_password)
        logger.debug(f"DAL.update_user_password returned: {update_success}")

        if not update_success:
             # This could happen if DAL reported no rows affected (user not found etc.), though NotFoundError above should cover user not found on hash retrieval.
             # This might indicate a DAL issue or a race condition.
             logger.error(f"DAL reported password update failed for user ID: {user_id}")
             # Re-fetch user to check existence? Or raise a specific DAL error?
             raise DALError(f"Failed to update password in database for user ID: {user_id}")
             
        logger.info(f"Password updated successfully for user ID: {user_id}")
        return True # Return True on successful update

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """
        Service layer function to delete a user.
        """
        logger.info(f"Attempting to delete user with ID: {user_id}")
        try:
            # Call DAL to delete user
            logger.debug(f"Calling DAL.delete_user for user ID: {user_id}")
            delete_success = await self.user_dal.delete_user(conn, user_id)
            logger.debug(f"DAL.delete_user returned: {delete_success}")

            if not delete_success:
                logger.warning(f"User not found during deletion for ID: {user_id}")
                raise NotFoundError(f"User with ID {user_id} not found for deletion.")

            logger.info(f"User deleted successfully with ID: {user_id}")
            return True
        except (NotFoundError) as e:
            logger.error(f"NotFoundError during user deletion for ID {user_id}: {e}")
            raise e
        except DALError as e:
            logger.error(f"Database error during user deletion for ID {user_id}: {e}")
            raise DALError(f"Database error during user deletion: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during user deletion for ID {user_id}: {e}")
            raise e

    async def request_verification_email(self, conn: pyodbc.Connection, email: str) -> dict:
        """
        Service layer function to request email verification link.
        """
        logger.info(f"Attempting to request verification email for email: {email}")
        try:
            # Call DAL to request verification link
            logger.debug(f"Calling DAL.request_verification_link for email: {email}")
            result = await self.user_dal.request_verification_link(conn, email)
            logger.debug(f"DAL.request_verification_link returned: {result}")
            
            # The DAL should handle cases like email not found or already verified.
            # If result indicates success (e.g., a link was generated/sent), return a success message.
            # The DAL stored procedure sp_RequestVerificationLink seems to return a message.
            # We can check the message or a specific status indicator if DAL provides one.
            # Assuming DAL returns a dictionary with a 'message' key on success/info.
            if result and isinstance(result, dict) and result.get('message'):
                 logger.info(f"Verification email request processed for email: {email}")
                 return result # Return the message from DAL
            else:
                 # This might indicate an issue in DAL even if no exception was raised.
                 logger.error(f"DAL.request_verification_link returned unexpected result for email {email}: {result}")
                 raise DALError(f"Failed to request verification email: Database process returned unexpected result.")

        except DALError as e:
            # Catch specific DAL errors (like disabled account handled in DAL SP)
            logger.error(f"Database error during verification email request for email {email}: {e}")
            raise e # Re-raise specific DAL errors like disabled account
        except Exception as e:
            logger.error(f"Unexpected error during verification email request for email {email}: {e}")
            raise e

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
        """
        Service layer function to verify email using a token.
        """
        logger.info(f"Attempting to verify email with token: {token}")
        try:
            # Call DAL to verify email
            logger.debug(f"Calling DAL.verify_email with token: {token}")
            result = await self.user_dal.verify_email(conn, token)
            logger.debug(f"DAL.verify_email returned: {result}")

            # The DAL stored procedure sp_VerifyEmail seems to return a dictionary with UserID and IsVerified.
            # We need to check if IsVerified is True.
            if result and isinstance(result, dict) and result.get('IsVerified') is True:
                logger.info(f"Email verified successfully with token: {token} for user ID: {result.get('UserID')}")
                return result # Return the result from DAL (including UserID and IsVerified=True)
            else:
                 # DAL should ideally raise an exception for invalid/expired token or disabled account.
                 # If it returns a dict but IsVerified is not True, it's an unexpected DAL outcome.
                 logger.error(f"DAL.verify_email returned unsuccessful verification result for token {token}: {result}")
                 # Re-check for specific DAL errors that might not have been raised?
                 if result and isinstance(result, dict) and result.get('message'):
                     # If DAL returned a message indicating failure, use it
                     raise DALError(f"邮箱验证失败: {result.get('message')}")
                 else:
                     # Generic DAL error if no specific message
                     raise DALError("邮箱验证失败: 数据库处理异常。")

        except DALError as e:
            # Catch specific DAL errors (like invalid/expired token, disabled account handled in DAL SP)
            logger.error(f"Database error during email verification with token {token}: {e}")
            raise e # Re-raise specific DAL errors
        except Exception as e:
            logger.error(f"Unexpected error during email verification with token {token}: {e}")
            raise e

    async def get_system_notifications(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """
        Service layer function to get system notifications for a user.
        """
        logger.info(f"Attempting to get system notifications for user ID: {user_id}")
        try:
            notifications = await self.user_dal.get_system_notifications_by_user_id(conn, user_id)
            logger.debug(f"DAL.get_system_notifications_by_user_id returned: {notifications}")
            # Assuming DAL returns a list of dictionaries
            return notifications
        except DALError as e:
            logger.error(f"Database error getting system notifications for user ID {user_id}: {e}")
            raise DALError(f"Database error getting system notifications: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting system notifications for user ID {user_id}: {e}")
            raise e

    async def mark_system_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        Service layer function to mark a system notification as read.
        """
        logger.info(f"Attempting to mark notification {notification_id} as read for user ID: {user_id}")
        try:
            success = await self.user_dal.mark_notification_as_read(conn, notification_id, user_id)
            logger.debug(f"DAL.mark_notification_as_read returned: {success}")
            if not success:
                logger.warning(f"Failed to mark notification {notification_id} as read for user ID {user_id}. Notification not found or not owned by user?")
                # Depending on DAL implementation, this might indicate NotFound or Forbidden
                # Re-fetching the notification to check ownership could be an option if needed
                # For now, just return False or raise a specific error if DAL doesn't already.
                # Assuming DAL returns False if not found or not updated.
                return False
            logger.info(f"Notification {notification_id} marked as read for user ID: {user_id}")
            return True
        except DALError as e:
            logger.error(f"Database error marking notification {notification_id} as read for user ID {user_id}: {e}")
            raise DALError(f"Database error marking notification as read: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error marking notification {notification_id} as read for user ID {user_id}: {e}")
            raise e

    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """
        Service layer function for admin to change user status.
        """
        logger.info(f"Admin {admin_id} attempting to change status of user {user_id} to {new_status}")
        # Optional: Add business logic validation for new_status if needed here
        try:
            success = await self.user_dal.change_user_status(conn, user_id, new_status, admin_id)
            logger.debug(f"DAL.change_user_status returned: {success}")
            if not success:
                 logger.warning(f"Failed to change status for user {user_id} by admin {admin_id}. User not found?")
                 raise NotFoundError(f"User with ID {user_id} not found for status change.")
            logger.info(f"User {user_id} status changed to {new_status} by admin {admin_id}")
            return True
        except (NotFoundError, ForbiddenError) as e:
            logger.error(f"Error changing status for user {user_id} by admin {admin_id}: {e}")
            raise e # Re-raise specific errors
        except DALError as e:
            logger.error(f"Database error changing status for user {user_id} by admin {admin_id}: {e}")
            raise DALError(f"Database error changing user status: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error changing status for user {user_id} by admin {admin_id}: {e}")
            raise e

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """
        Service layer function for admin to adjust user credit.
        """
        logger.info(f"Admin {admin_id} attempting to adjust credit for user {user_id} by {credit_adjustment} with reason: {reason}")
        # Optional: Add business logic validation for credit_adjustment or reason
        try:
            success = await self.user_dal.adjust_user_credit(conn, user_id, credit_adjustment, admin_id, reason)
            logger.debug(f"DAL.adjust_user_credit returned: {success}")
            if not success:
                 logger.warning(f"Failed to adjust credit for user {user_id} by admin {admin_id}. User not found?")
                 raise NotFoundError(f"User with ID {user_id} not found for credit adjustment.")
            logger.info(f"User {user_id} credit adjusted by {credit_adjustment} by admin {admin_id}")
            return True
        except (NotFoundError, ForbiddenError) as e:
            logger.error(f"Error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise e # Re-raise specific errors
        except DALError as e:
            logger.error(f"Database error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise DALError(f"Database error adjusting user credit: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise e

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[UserResponseSchema]:
        """
        Service layer function for admin to get all users.
        """
        logger.info(f"Admin {admin_id} attempting to get all users.")
        try:
            dal_users = await self.user_dal.get_all_users(conn, admin_id)
            logger.debug(f"DAL.get_all_users returned {len(dal_users)} users.")

            # Convert DAL user dictionaries to UserResponseSchema
            users = [self._convert_dal_user_to_schema(user_data) for user_data in dal_users]
            logger.info(f"Successfully retrieved and converted {len(users)} users for admin {admin_id}.")
            return users
        except ForbiddenError as e:
             logger.error(f"Admin {admin_id} ForbiddenError getting all users: {e}")
             raise e
        except DALError as e:
            logger.error(f"Database error getting all users for admin {admin_id}: {e}")
            raise DALError(f"Database error getting all users: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting all users for admin {admin_id}: {e}")
            raise e

    def _map_dal_keys_to_schema_keys(self, dal_user_data: dict) -> dict:
        """Maps DAL dictionary keys (potential SQL column names/aliases) to UserResponseSchema field names."""
        if not dal_user_data:
            return {}

        mapped_data = {}
        # Define mapping from schema field name to a list of potential DAL dictionary keys
        # Include snake_case as a potential key name as well
        key_mapping = {
            "user_id": ["UserID", "用户ID", "user_id"], # Add snake_case
            "username": ["UserName", "用户名", "username"], # Add snake_case
            "email": ["Email", "邮箱", "email"], # Add snake_case
            "status": ["Status", "账户状态", "status"], # Add snake_case
            "credit": ["Credit", "信用分", "credit"], # Add snake_case
            "is_staff": ["IsStaff", "是否管理员", "is_staff"], # Add snake_case
            "is_verified": ["IsVerified", "是否已认证", "is_verified"], # Add snake_case
            "major": ["Major", "专业", "major"], # Add snake_case
            "avatar_url": ["AvatarUrl", "头像URL", "avatar_url"], # Add snake_case
            "bio": ["Bio", "个人简介", "bio"], # Add snake_case
            "phone_number": ["PhoneNumber", "手机号码", "phone_number"], # Add snake_case
            "join_time": ["JoinTime", "注册时间", "join_time"], # Add snake_case
        }

        for schema_key, dal_keys in key_mapping.items():
            for dal_key in dal_keys:
                # Check if the key exists AND the value is not None
                if dal_key in dal_user_data and dal_user_data[dal_key] is not None:
                    mapped_data[schema_key] = dal_user_data[dal_key]
                    break # Found a valid value, move to the next schema key
                # If the key exists but the value is None, we explicitly set it to None
                elif dal_key in dal_user_data and dal_user_data[dal_key] is None:
                     mapped_data[schema_key] = None
                     # If the key exists with None value, we still map it as None and break
                     # This ensures Optional fields are explicitly set to None if they are NULL in DB
                     break
            # If the loop finishes and the schema_key is not in mapped_data, it means none of the dal_keys were found.
            # Pydantic will handle this for Optional fields by defaulting to None.
            # For required fields, this would lead to a validation error.

        return mapped_data

    # Helper method to convert DAL dictionary to UserResponseSchema (defined earlier)
    def _convert_dal_user_to_schema(self, dal_user_data: dict) -> UserResponseSchema:
        """Converts a dictionary from DAL to a UserResponseSchema Pydantic model."""
        if not dal_user_data:
             # Handle case where DAL returns no data for a single entity fetch (e.g., user not found)
             # This should ideally be caught by DAL/Service before conversion, but adding a safeguard.
             logger.warning("Attempted to convert empty DAL data to UserResponseSchema")
             # Depending on context, you might return None, raise NotFoundError, or return a default schema.
             # Given this is for conversion *after* data is fetched, returning None or raising is appropriate.
             # Raising an error here if data is expected is better for debugging upstream issues.
             raise DALError("Cannot convert empty database result to UserResponseSchema") # Indicate issue with data retrieval

        try:
            # Use the robust mapping helper
            mapped_data = self._map_dal_keys_to_schema_keys(dal_user_data)

            # Create and return the Pydantic model instance
            # Pydantic will perform validation. Required fields missing in mapped_data or mapped as None will cause validation errors.
            # With UserResponseSchema fields now being Optional, None values from DAL will be accepted.
            return UserResponseSchema(**mapped_data)

        except Exception as e:
            # Log the error and the data that caused it
            loggable_data = {k: str(v) if isinstance(v, UUID) else v for k, v in dal_user_data.items()} if dal_user_data else None
            logger.error(f"Error converting DAL user data to schema: {e}. Data: {loggable_data}")
            # Re-raise the error, ensuring Pydantic validation errors are distinguishable if needed
            # For now, wrapping in DALError is consistent.
            raise DALError(f"Failed to process user data for schema conversion: {e}") from e

# TODO: Add service functions for admin operations (get all users, disable/enable user etc.)