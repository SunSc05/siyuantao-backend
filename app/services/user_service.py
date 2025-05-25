# app/services/user_service.py
import pyodbc
from uuid import UUID
from typing import Optional
import logging

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
        # Business logic / validation can go here (e.g., check password strength)

        hashed_password = get_password_hash(user_data.password)

        try:
            # Call DAL to create user
            # The DAL method is expected to return a dictionary representation of the created user
            # Or raise IntegrityError for duplicates or DALError for other DB issues
            created_user = await self.user_dal.create_user(
                conn,
                user_data.username,
                hashed_password,
                user_data.phone_number,
                major=user_data.major
            )

            # After successful creation in DAL, fetch the complete user profile
            # This is needed to populate all fields for UserResponseSchema, including default values etc.
            # Assuming DAL.get_user_by_id returns a dictionary matching _convert_dal_user_to_schema expectations
            # The DAL create_user method should ideally return the newly created user's ID or complete data,
            # but if not, a subsequent fetch by username or ID is necessary.
            # Let's adjust based on the assumption that DAL.create_user returns the dictionary directly.
            # If DAL.create_user only returns ID, we would need get_user_profile_by_id here.
            # Based on test mocks, DAL.create_user is mocked to return the full dict.

            # Convert the DAL dictionary result to a dictionary matching UserResponseSchema keys
            # The DAL method is expected to return a dictionary already suitable for conversion
            converted_user_data = self._convert_dal_user_to_schema(created_user) # Convert DAL dict to schema dict

            # Return the UserResponseSchema instance
            # The Router will handle converting this Pydantic model to JSON response
            return converted_user_data # Return the converted dict

        except (IntegrityError, NotFoundError) as e:
            # Re-raise specific exceptions from DAL
            raise e
        except DALError as e:
            # Wrap general DAL errors in a Service layer error with more context
            logging.error(f"Database error during user creation for {user_data.username}: {e}")
            raise DALError(f"Database error during user creation: {e}") from e # Wrap and re-raise
        except Exception as e:
            # Catch any other unexpected errors
            logging.error(f"Unexpected error during user creation for {user_data.username}: {e}")
            raise e # Re-raise other unexpected errors

    async def authenticate_user_and_create_token(self, conn: pyodbc.Connection, username: str, password: str) -> str:
        """
        Service layer function to authenticate a user and generate a JWT token.
        Calls DAL to get user, verifies password, checks status, and creates token.
        """
        # 1. Call DAL to get user with password hash
        user = await self.user_dal.get_user_by_username_with_password(conn, username)
        if not user:
            # User not found
            raise AuthenticationError("用户名或密码不正确")

        # 2. Verify password
        stored_password_hash = user.get('Password')
        if not stored_password_hash or not verify_password(password, stored_password_hash):
            # Password doesn't match
            raise AuthenticationError("用户名或密码不正确")

        # 3. Check user status (e.g., Disabled) - Business logic in Service
        if user.get('Status') == 'Disabled':
            raise ForbiddenError("账户已被禁用") # Raise a specific exception

        # TODO: Check if user is verified if verification is required for login
        # if not user.get('IsVerified') and require_verification:
        #     raise ForbiddenError("邮箱未验证，请先验证邮箱")

        # 4. Create JWT Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Use user data (like UserID, IsStaff) to create the token payload
        # Ensure UserID is correctly accessed from the user dict returned by DAL
        user_id = user.get('UserID') # Assuming DAL returns 'UserID'
        is_staff = user.get('IsStaff', False) # Assuming DAL returns 'IsStaff'
        is_verified = user.get('IsVerified', False) # Assuming DAL returns 'IsVerified'

        if not user_id:
             # This should not happen if DAL works correctly
             raise DALError("Failed to retrieve UserID for token creation after authentication.")

        access_token = create_access_token(
            data={
                "user_id": str(user_id), # Ensure user_id is string in token
                "is_staff": is_staff,
                "is_verified": is_verified # Include verification status in token
            },
            expires_delta=access_token_expires
        )
        return access_token # Return the token string

    async def get_user_profile_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> UserResponseSchema:
        """
        Service layer function to get user profile by ID.
        Handles NotFoundError from DAL.
        """
        print(f"DEBUG Service: get_user_profile_by_id received user_id: {user_id} (type: {type(user_id)})") # Debug print
        # Pass the connection to the DAL method
        user = await self.user_dal.get_user_by_id(conn, user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found.")
        
        # Convert DAL response keys to match UserResponseSchema
        return self._convert_dal_user_to_schema(user) # Return the converted dict

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, user_update_data: UserProfileUpdateSchema) -> UserResponseSchema:
        """
        Service layer function to update user profile.
        Extracts updated fields and calls DAL.
        """
        print(f"DEBUG Service: update_user_profile received user_id: {user_id} (type: {type(user_id)})") # Debug print
        # Extract only the fields that are set in the UserProfileUpdateSchema
        update_data = user_update_data.model_dump(exclude_unset=True)

        # If no fields are actually being updated, maybe return the current user profile?
        if not update_data:
             # Fetch and return the current user profile
             return await self.get_user_profile_by_id(conn, user_id)

        try:
            # Call DAL to perform the update
            # Pass fields individually as required by DAL.update_user_profile
            # Pass the connection to the DAL method
            updated_user = await self.user_dal.update_user_profile(
                conn, user_id,
                major=update_data.get('major'),
                avatar_url=update_data.get('avatar_url'),
                bio=update_data.get('bio'),
                phone_number=update_data.get('phone_number')
            )
            # DAL is expected to raise NotFoundError if user_id does not exist
            # DAL is expected to raise IntegrityError for duplicate phone number
            # DAL.update_user_profile is designed to return the updated user dict on success or raise exception.

            if not updated_user:
                 # This indicates an unexpected issue in DAL or SP - fallback to re-fetch
                 print(f"WARNING: DAL.update_user_profile returned None unexpectedly for user {user_id}")
                 # Re-fetch and convert before returning
                 return self._convert_dal_user_to_schema(await self.user_dal.get_user_by_id(conn, user_id)) # Re-fetch to be sure

            # Convert DAL response keys to match UserResponseSchema
            return self._convert_dal_user_to_schema(updated_user)

        except (NotFoundError, IntegrityError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL
        except Exception as e:
            print(f"ERROR: Unexpected error in update_user_profile service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, password_update_data: UserPasswordUpdate) -> bool:
        """
        Service layer function to update user password.
        Verifies old password and calls DAL.
        """
        print(f"DEBUG Service: update_user_password received user_id: {user_id} (type: {type(user_id)})") # Debug print
        # 1. Get user with password hash to verify old password
        # Use the DAL method that gets user data including the password hash by UserID
        # Need to implement get_user_by_id_with_password in DAL if not exists
        # A more efficient way would be a DAL method by ID.

        # Let's stick to the existing DAL method for now, but it requires getting username first.
        # Pass the connection to the DAL method
        current_user_profile = await self.user_dal.get_user_by_id(conn, user_id) # Will raise NotFoundError if user doesn't exist
        username = current_user_profile.get('用户名') # Assuming DAL returns '用户名'

        if not username:
             # This indicates an issue in get_user_by_id or the SP
             raise DALError("Failed to retrieve username for password update.") # Unexpected issue

        # Now get user with password hash using the username
        # Pass the connection to the DAL method
        user_with_password_hash = await self.user_dal.get_user_by_username_with_password(conn, username)

        # Ensure we found the user and it's the correct user
        if not user_with_password_hash or user_with_password_hash.get('UserID') != user_id:
             # This indicates a major inconsistency, perhaps user was deleted concurrently?
             raise NotFoundError(f"User with ID {user_id} not found or data inconsistent during password update.")

        stored_password_hash = user_with_password_hash.get('Password')

        # 1. Verify old password
        if not stored_password_hash or not verify_password(password_update_data.old_password, stored_password_hash):
            raise AuthenticationError("旧密码不正确") # Raise a specific authentication error

        # 2. Hash new password
        new_hashed_password = get_password_hash(password_update_data.new_password)

        # 3. Call DAL to update password
        try:
            # Pass the connection to the DAL method
            update_success = await self.user_dal.update_user_password(
                conn,
                user_id,
                new_hashed_password
            )
            # DAL.update_user_password is expected to raise NotFoundError or DALError on failure
            # It returns True on success.
            if not update_success:
                 raise DALError("密码更新失败：数据库操作未能完成。") # Unexpected DAL failure

            return True # Password update successful

        except (NotFoundError, AuthenticationError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL or AuthenticationError
        except Exception as e:
            print(f"ERROR: Unexpected error in update_user_password service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """
        Service layer function to delete a user by ID.
        Handles NotFoundError from DAL.
        """
        print(f"DEBUG Service: delete_user received user_id: {user_id} (type: {type(user_id)})") # Debug print
        try:
            # Pass the connection to the DAL method
            delete_success = await self.user_dal.delete_user(conn, user_id)
            # DAL.delete_user is expected to raise NotFoundError if user doesn't exist
            # It returns True on success.
            if not delete_success:
                 raise DALError("用户删除失败：数据库操作未能完成或用户不存在(意外)。") # Unexpected DAL failure

            return True # User deleted successfully

        except (NotFoundError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL
        except Exception as e:
            print(f"ERROR: Unexpected error in delete_user service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def request_verification_email(self, conn: pyodbc.Connection, email: str) -> dict:
         """
         Service layer function to handle request for email verification link.
         Calls DAL and can potentially trigger email sending (TODO).
         """
         try:
             # Pass the connection to the DAL method
             linkage_result = await self.user_dal.request_verification_link(
                 conn,
                 email
             )
             # DAL.request_verification_link is expected to raise DALError for disabled account
             # It returns a dict with VerificationToken, UserID, IsNewUser on success (or if email doesn't exist, creates user).

             # TODO: Trigger actual email sending here using the VerificationToken from linkage_result
             # send_email(linkage_result.get('email', email), linkage_result.get('VerificationToken'))
             print(f"DEBUG: Email verification link requested for {email}.")

             # Return the result including token, user_id, is_new_user (no schema conversion needed for this endpoint response)
             return linkage_result 

         except DALError as e:
             # DALError from request_verification_link indicates SP-level business rule violation (like disabled account)
             raise e # Re-raise DALError (Router will convert to HTTP exception)
         except Exception as e:
             print(f"ERROR: Unexpected error in request_verification_email service for email {email}: {e}")
             raise e # Re-raise other unexpected errors

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
         """
         Service layer function to handle email verification with token.
         Calls DAL to verify token.
         """
         try:
             # Pass the connection to the DAL method
             verification_result = await self.user_dal.verify_email(
                 conn,
                 token
             )
             # DAL.verify_email is expected to raise DALError for invalid/expired token or disabled account.
             # It returns a dict with UserID, IsVerified on success.

             if not verification_result or verification_result.get('IsVerified') is not True:
                  # This case should ideally be covered by DAL errors, but as a safeguard
                  raise DALError("Email verification failed: Unexpected result from database.")

             return verification_result # Return dict with UserID, IsVerified=True

         except DALError as e:
             # DALError from verify_email indicates SP-level business rule violation (invalid/expired token, disabled account)
             raise e # Re-raise DALError
         except Exception as e:
             print(f"ERROR: Unexpected error in verify_email service for token {token}: {e}")
             raise e # Re-raise other unexpected errors

    # New Service methods for system notifications
    async def get_system_notifications(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """
        Service layer function to get system notifications for a user.
        Calls DAL.
        """
        # DAL is expected to handle NotFoundError for user
        return await self.user_dal.get_system_notifications_by_user_id(conn, user_id)

    async def mark_system_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        Service layer function to mark a system notification as read.
        Calls DAL.
        Handles NotFoundError and ForbiddenError from DAL.
        """
        # DAL is expected to handle NotFoundError (notification not found) and ForbiddenError (user mismatch)
        return await self.user_dal.mark_notification_as_read(conn, notification_id, user_id)

    # New Service methods for admin user management
    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """管理员禁用/启用用户账户。"""
        print(f"DEBUG Service: change_user_status received user_id: {user_id} (type: {type(user_id)}), admin_id: {admin_id} (type: {type(admin_id)})") # Debug print
        sql = "{CALL sp_ChangeUserStatus(?, ?, ?)}"
        try:
            # Use the injected execute_query function
            # sp_ChangeUserStatus returns a success message or raises errors
            result = await self.user_dal.change_user_status(conn, user_id, new_status, admin_id) # Call the DAL method

            # DAL.change_user_status is expected to raise NotFoundError, ForbiddenError, or DALError on failure
            # It returns True on success.
            if not result:
                 # This case should ideally be covered by exceptions from DAL, but as a safeguard
                 raise DALError("用户状态更改失败：数据库操作未能完成或用户不存在/无权限(意外)。") # Unexpected DAL failure

            return True # Status change successful

        except (NotFoundError, ForbiddenError, DALError) as e:
            # Catch specific exceptions from DAL and potentially re-raise or convert
            # For specific DAL errors related to invalid status, re-raise as ValueError or similar
            if isinstance(e, DALError) and "无效的用户状态" in str(e):
                raise ValueError(str(e)) from e # Convert specific DALError to ValueError
            raise e # Re-raise NotFoundError, ForbiddenError, or other DALError
        except Exception as e:
            print(f"ERROR: Unexpected error in change_user_status service for user {user_id}, admin {admin_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """
        管理员手动调整用户信用分。
        """
        print(f"DEBUG Service: adjust_user_credit received user_id: {user_id} (type: {type(user_id)}), admin_id: {admin_id} (type: {type(admin_id)})") # Debug print
        # Business logic validation (e.g., credit bounds) could go here if not handled by DAL/SP
        # if not 0 <= (current_credit + credit_adjustment) <= 100:
        #     raise ValueError("信用分调整超出允许范围 (0-100).") # Example validation

        sql = "{CALL sp_AdjustUserCredit(?, ?, ?, ?)}"
        try:
            # Use the injected execute_query function
            # sp_AdjustUserCredit returns a success message or raises errors
            result = await self.user_dal.adjust_user_credit(conn, user_id, credit_adjustment, admin_id, reason) # Call the DAL method

            # DAL.adjust_user_credit is expected to raise NotFoundError, ForbiddenError, or DALError on failure
            # It returns True on success.
            if not result:
                 # This case should ideally be covered by exceptions from DAL, but as a safeguard
                 raise DALError("用户信用分调整失败：数据库操作未能完成或用户不存在/无权限(意外)。") # Unexpected DAL failure

            return True # Credit adjustment successful

        except (NotFoundError, ForbiddenError, DALError) as e:
            # Catch specific exceptions from DAL and potentially re-raise or convert
            # For specific DAL errors related to credit limits or missing reason, re-raise as ValueError or similar
            if isinstance(e, DALError):
                if "信用分不能超过100" in str(e) or "信用分不能低于0" in str(e):
                    raise ValueError(str(e)) from e # Convert credit limit errors to ValueError
                if "调整信用分必须提供原因" in str(e):
                    raise ValueError(str(e)) from e # Convert missing reason error to ValueError
            raise e # Re-raise NotFoundError, ForbiddenError, or other DALError
        except Exception as e:
            print(f"ERROR: Unexpected error in adjust_user_credit service for user {user_id}, admin {admin_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[UserResponseSchema]:
        """Service layer function for admin to get all users.
        Calls DAL and handles permissions/errors."""
        print(f"DEBUG Service: get_all_users received admin_id: {admin_id} (type: {type(admin_id)})") # Debug print
        try:
            # DAL layer is expected to handle admin permission check and potential errors
            users = await self.user_dal.get_all_users(conn, admin_id)

            # Convert each user dict in the list
            converted_users = [self._convert_dal_user_to_schema(user) for user in users] if users else [] # Handle empty list case
            return converted_users # Returns a list of converted user dictionaries

        except (ForbiddenError, NotFoundError, DALError) as e:
            # Re-raise specific exceptions from DAL
            raise e
        except Exception as e:
            print(f"ERROR: Unexpected error in get_all_users service for admin {admin_id}: {e}")
            raise e # Re-raise other unexpected errors

    def _convert_dal_user_to_schema(self, dal_user_data: dict) -> UserResponseSchema:
        """Converts a dictionary from DAL (potentially with DB keys) to a UserResponseSchema instance."""
        if not dal_user_data:
            # If dal_user_data is unexpectedly empty or None, raise a clearer error
            raise DALError("Cannot convert empty or None DAL user data to UserResponseSchema.")
            
        # Define mapping from potential DAL keys to UserResponseSchema keys
        # Ensure this mapping is correct based on the actual keys returned by your stored procedures or DAL
        # Assuming English keys as defined in the DAL test mocks now.
        key_mapping = {
            'user_id': 'user_id',
            'username': 'username',
            'email': 'email', 
            'status': 'status',
            'credit': 'credit',
            'is_staff': 'is_staff',
            'is_verified': 'is_verified',
            'major': 'major',
            'avatar_url': 'avatar_url',
            'bio': 'bio',
            'phone_number': 'phone_number',
            'join_time': 'join_time',
            # Add other potential keys if necessary
        }

        # Create a new dictionary with schema-compatible keys, fetching values from dal_user_data
        schema_data = {}
        for dal_key, schema_key in key_mapping.items():
            # Use .get() with a default of None in case a key is missing in the DAL dict
            # Use schema_key as the key in schema_data
            value = dal_user_data.get(dal_key)
            # Include None values for optional fields to match schema structure
            schema_data[schema_key] = value 
            

        # Return a UserResponseSchema instance directly from the converted data
        # Pydantic should handle conversion of UUID string and datetime object/string
        try:
            # Create and validate the schema instance
            # Ensure all required fields for UserResponseSchema are present in schema_data
            # Pydantic will handle validation and type casting
            return UserResponseSchema(**schema_data)
        except Exception as e:
            # Log potential validation errors during conversion
            logging.error(f"Failed to convert DAL user data to UserResponseSchema: {e} for data: {schema_data}")
            # Re-raise as a Service layer error, possibly with more context
            raise DALError(f"Failed to process user data from database: {e}") from e

# TODO: Add service functions for admin operations (get all users, disable/enable user etc.)